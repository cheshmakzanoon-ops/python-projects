from __future__ import annotations

import asyncio

import pytest

from pp_proving_ground.serving.body_limit import BodyLimitMiddleware


@pytest.mark.parametrize("chunks", [[b"1234", b"5678"], [b"12345678"], [b"", b""]])
def test_body_limit_replays_complete_body_at_or_below_limit(chunks):
    received, responses = [], []

    async def application(scope, receive, send):
        message = await receive()
        received.append(message["body"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def exercise():
        messages = iter(
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        )

        async def receive():
            return next(messages)

        async def send(message):
            responses.append(message)

        await BodyLimitMiddleware(application, max_bytes=8)({"type": "http"}, receive, send)

    asyncio.run(exercise())
    assert received == [b"".join(chunks)]
    assert responses[0]["status"] == 200


@pytest.mark.parametrize("chunks", [[b"1234", b"56789"], [b"123456789"]])
def test_oversize_body_is_rejected_before_dispatch(chunks):
    responses = []

    async def application(scope, receive, send):
        pytest.fail("oversize input reached the application")

    async def exercise():
        messages = iter(
            {"type": "http.request", "body": chunk, "more_body": True} for chunk in chunks
        )

        async def receive():
            return next(messages)

        async def send(message):
            responses.append(message)

        await BodyLimitMiddleware(application, max_bytes=8)({"type": "http"}, receive, send)

    asyncio.run(exercise())
    assert responses[0]["status"] == 413


def test_disconnected_partial_request_is_not_dispatched():
    async def application(scope, receive, send):
        pytest.fail("disconnected input reached the application")

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        pytest.fail("a response was sent to a disconnected client")

    asyncio.run(BodyLimitMiddleware(application)({"type": "http"}, receive, send))
