"""Browser response policy for a bearer-authenticated local application."""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BrowserSecurityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                if scope["path"] == "/" or scope["path"].startswith("/assets/"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; script-src 'self'; style-src 'self'; "
                        "connect-src 'self'; base-uri 'none'; form-action 'self'; "
                        "frame-ancestors 'none'"
                    )
            await send(message)

        await self.app(scope, receive, secured_send)
