"""Receive-level body limits, including missing Content-Length."""

import asyncio

from pp_atlas.api.body_limit import BodyLimitMiddleware


def test_unknown_length_enforced_across_chunks() -> None:
    async def app(scope, receive, send):
        raise AssertionError("oversized request must not reach application")

    messages = iter(
        (
            {"type": "http.request", "body": b"a" * 3, "more_body": True},
            {"type": "http.request", "body": b"b" * 4, "more_body": False},
        )
    )

    async def receive():
        return next(messages)

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(
        BodyLimitMiddleware(app, max_bytes=5)({"type": "http", "headers": []}, receive, send)
    )
    assert sent[0]["status"] == 413
    assert b"limit" in sent[-1]["body"]


def test_large_content_length_is_rejected_before_application() -> None:
    async def app(scope, receive, send):
        raise AssertionError("application must not run")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(
        BodyLimitMiddleware(app, max_bytes=3)(
            {"type": "http", "headers": [(b"content-length", b"100")]}, receive, send
        )
    )
    assert sent[0]["status"] == 413
