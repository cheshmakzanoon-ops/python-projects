"""ASGI receive-level request size limit without Starlette private attributes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app: Any, max_bytes: int = 2_100_000) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        content_lengths = [
            value for key, value in scope.get("headers", ()) if key.lower() == b"content-length"
        ]
        if len(content_lengths) > 1:
            await JSONResponse({"detail": "invalid content-length"}, status_code=400)(
                scope, receive, send
            )
            return
        if content_lengths:
            try:
                value = int(content_lengths[0])
                if value < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse({"detail": "invalid content-length"}, status_code=400)(
                    scope, receive, send
                )
                return
            if value > self.max_bytes:
                await JSONResponse({"detail": "request body exceeds limit"}, status_code=413)(
                    scope, receive, send
                )
                return
        consumed = 0
        started = False

        async def bounded_receive() -> dict[str, Any]:
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracked_send(message: dict[str, Any]) -> None:
            nonlocal started
            if message.get("type") == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except _BodyTooLarge:
            if started:
                # Cannot send a second status after an HTTP response has begun.
                raise
            await JSONResponse({"detail": "request body exceeds limit"}, status_code=413)(
                scope, receive, send
            )
