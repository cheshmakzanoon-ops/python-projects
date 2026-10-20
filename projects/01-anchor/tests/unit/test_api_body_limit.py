"""Exercise ASGI framing directly, independently of test-client normalization."""

import asyncio

import pytest
from starlette.responses import Response

from pp_anchor.api.body_limit import BodyLimitMiddleware


def request(messages, *, headers=(), max_bytes=8, method="GET", path="/health"):
    incoming = iter(messages)
    outgoing = []
    bodies = []

    async def receive():
        return next(incoming)

    async def send(message):
        outgoing.append(message)

    async def application(scope, receive, send):
        if scope["type"] != "http":
            bodies.append(scope["type"])
            return
        message = await receive()
        bodies.append(message["body"])
        assert not message["more_body"]
        await Response("ok")(scope, receive, send)

    scope = {"type": "http", "headers": headers, "method": method, "path": path}
    asyncio.run(BodyLimitMiddleware(application, max_bytes)(scope, receive, send))
    return outgoing, bodies


def test_chunked_body_is_replayed_once_without_private_request_state():
    outgoing, bodies = request(
        [
            {"type": "http.request", "body": b"first", "more_body": True},
            {"type": "http.request", "body": b"two", "more_body": False},
        ]
    )
    assert outgoing[0]["status"] == 200
    assert bodies == [b"firsttwo"]


def test_chunked_oversize_is_rejected_before_application_runs():
    outgoing, bodies = request(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"6789", "more_body": False},
        ]
    )
    assert outgoing[0]["status"] == 413
    assert bodies == []


@pytest.mark.parametrize("value", [b"-1", b"1.0", b"+1", b"x", b"", b" 1"])
def test_invalid_content_length_is_rejected_without_reading(value):
    outgoing, bodies = request([], headers=[(b"content-length", value)])
    assert outgoing[0]["status"] == 400
    assert bodies == []


@pytest.mark.parametrize("value", [b"9", b"9" * 5000])
def test_declared_oversize_is_rejected_without_reading(value):
    outgoing, bodies = request([], headers=[(b"content-length", value)])
    assert outgoing[0]["status"] == 413
    assert bodies == []


def test_duplicate_content_length_and_short_body_are_rejected():
    outgoing, _ = request([], headers=[(b"content-length", b"0"), (b"Content-Length", b"0")])
    assert outgoing[0]["status"] == 400
    outgoing, bodies = request(
        [{"type": "http.request", "body": b"a"}], headers=[(b"content-length", b"2")]
    )
    assert outgoing[0]["status"] == 400
    assert bodies == []


def test_disconnected_body_does_not_enter_application():
    outgoing, bodies = request(
        [
            {"type": "http.request", "body": b"first", "more_body": True},
            {"type": "http.disconnect"},
        ]
    )
    assert outgoing == []
    assert bodies == []


def test_non_http_scope_passes_through():
    observed = []

    async def application(scope, receive, send):
        observed.append(scope["type"])

    async def unused():
        raise AssertionError("must not receive")

    asyncio.run(BodyLimitMiddleware(application)({"type": "lifespan"}, unused, unused))
    assert observed == ["lifespan"]


@pytest.mark.parametrize(
    "body",
    [
        b'{"payload":{"text":"\\u0000"}}',
        b'{"payload":{"text":"\\ud800"}}',
        b'{"payload":{"text":NaN}}',
        b'{"payload":{"text":Infinity}}',
        b'{"payload":{"text":1e999}}',
        b'{"idempotency_key":"first","idempotency_key":"second"}',
        b'{"payload":' + b"[" * 2_000 + b"0" + b"]" * 2_000 + b"}",
    ],
)
def test_invalid_json_is_rejected_before_routing(body):
    outgoing, bodies = request(
        [{"type": "http.request", "body": body}],
        max_bytes=10_000,
        method="POST",
        path="/runs",
    )
    assert outgoing[0]["status"] == 422
    assert bodies == []


def test_health_get_does_not_parse_or_reinterpret_a_body():
    outgoing, bodies = request(
        [{"type": "http.request", "body": b"not-json"}],
        max_bytes=100,
    )
    assert outgoing[0]["status"] == 200
    assert bodies == [b"not-json"]
