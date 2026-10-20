"""Malformed requests must fail before persistence or interpreter recursion."""

import json

import pytest

from pp_meridian.api.validation import MAX_OFFSET, json_object, pagination


@pytest.mark.parametrize(
    "body",
    [
        b'{"name":"first","name":"second"}',
        b'{"postings":[{"amount":"1.00","amount":"2.00"}]}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":1e999}',
        b'{"name":"null\\u0000byte"}',
        b'{"name":"unpaired\\ud800"}',
        b'{"\\udc00":"invalid key"}',
        b'{"unknown":["\\ud800"]}',
        b'{"unknown":["\\u0000"]}',
        b'{"name":"\xff"}',
        b"[]",
        b"null",
        b'"string"',
    ],
)
def test_rejects_ambiguous_or_nonrepresentable_json(body):
    with pytest.raises(ValueError):
        json_object(body)


@pytest.mark.parametrize("depth", [32, 2_000])
def test_rejects_excessively_nested_json_without_recursion_failure(depth):
    body = b'{"unknown":' + b"[" * depth + b"0" + b"]" * depth + b"}"
    with pytest.raises(ValueError, match="nesting"):
        json_object(body)


def test_accepts_utf8_unicode_and_escaped_surrogate_pairs():
    payload = {"name": "Montréal 🏦", "metadata": [1.5, True, None, {"key": "value"}]}
    assert json_object(json.dumps(payload).encode()) == payload
    assert json_object(json.dumps(payload, ensure_ascii=False).encode()) == payload
    assert json_object(b"") == {}


def test_enforces_body_size_before_parsing():
    with pytest.raises(ValueError, match="too large"):
        json_object(b" " * 1_000_001)


@pytest.mark.parametrize(
    "offset,limit", [(str(MAX_OFFSET + 1), "1"), ("-1", "1"), ("0", "0"), ("0", "101")]
)
def test_pagination_rejects_database_overflow_and_invalid_ranges(offset, limit):
    with pytest.raises(ValueError):
        pagination(offset, limit)


def test_pagination_accepts_postgresql_bigint_boundary():
    assert pagination(str(MAX_OFFSET), "100") == (MAX_OFFSET, 100)
