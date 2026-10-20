"""Bound the complete HTTP body before dispatch using the public ASGI protocol."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 2 * 1024 * 1024) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("body limit must be a positive integer")
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        payload = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(payload) + len(chunk) > self.max_bytes:
                await JSONResponse({"detail": "request body exceeds 2 MiB"}, status_code=413)(
                    scope, receive, send
                )
                return
            payload.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(payload), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
