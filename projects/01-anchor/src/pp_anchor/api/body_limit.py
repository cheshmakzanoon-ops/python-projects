"""Bound HTTP requests before routing, using the public ASGI message protocol."""

import json

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pp_anchor.definitions.model import canonical


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object member")
        result[key] = value
    return result


class BodyLimitMiddleware:
    """Buffer at most one bounded request, including chunked request bodies.

    Validate framing before application code runs. Replaying one ASGI request
    message avoids relying on Starlette's private request-body cache.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = 1_048_576) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        lengths = [value for name, value in scope["headers"] if name.lower() == b"content-length"]
        declared: int | None = None
        if lengths:
            value = lengths[0]
            if len(lengths) != 1 or not value.isdigit():
                await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(
                    scope, receive, send
                )
                return
            # Compare digit strings before conversion: an attacker-controlled
            # header must not exceed Python's integer-string conversion limit.
            digits = value.lstrip(b"0") or b"0"
            maximum = str(self.max_bytes).encode("ascii")
            if len(digits) > len(maximum) or (len(digits) == len(maximum) and digits > maximum):
                await self._too_large(scope, receive, send)
                return
            declared = int(digits)

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                await self._too_large(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        if declared is not None and declared != len(body):
            await JSONResponse({"detail": "Content-Length does not match body"}, status_code=400)(
                scope, receive, send
            )
            return

        path = scope.get("path", "")
        root_path = scope.get("root_path", "")
        if root_path and path.startswith(root_path + "/"):
            path = path[len(root_path) :]
        json_route = path == "/runs" or (path.startswith("/runs/") and path.endswith("/signals"))
        if scope.get("method") == "POST" and json_route and body:
            try:
                # Validate before FastAPI's parser can exhaust recursion and
                # before PostgreSQL can reject null/surrogate text as a 500.
                value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
                canonical(value)
            except (ValueError, RecursionError) as exc:
                detail = (
                    "JSON nesting exceeds 64 levels"
                    if isinstance(exc, RecursionError)
                    else str(exc)
                )
                await JSONResponse({"detail": detail}, status_code=422)(scope, receive, send)
                return

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)

    async def _too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"detail": "Request exceeds 1 MiB"}, status_code=413)(
            scope, receive, send
        )
