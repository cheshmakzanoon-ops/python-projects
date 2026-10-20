"""Bounded, unambiguous JSON and pagination at the HTTP boundary."""

import json
import math
from typing import NoReturn, cast

MAX_BODY_BYTES = 1_000_000
MAX_JSON_DEPTH = 32
MAX_OFFSET = 2**63 - 1


def _reject_constant(value: str) -> NoReturn:
    raise ValueError("JSON numbers must be finite")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON numbers must be finite")
    return number


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object member")
        result[key] = value
    return result


def json_object(body: bytes) -> dict[str, object]:
    """Reject inputs with parser-dependent meaning before any database writes.

    PostgreSQL text cannot represent null bytes or unpaired Unicode surrogates.
    Validate all strings, including unknown fields, rather than relying on a
    driver error inside a transaction. Use an iterative depth check so deeply
    nested input never becomes an uncaught Python recursion failure.
    """
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("request too large")
    try:
        value = json.loads(
            (body or b"{}").decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds 32 levels") from error
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if isinstance(current, (dict, list)):
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting exceeds 32 levels")
            children = (
                [*current.keys(), *current.values()] if isinstance(current, dict) else current
            )
            pending.extend((child, depth + 1) for child in children)
        elif isinstance(current, str):
            if "\x00" in current:
                raise ValueError("JSON strings cannot contain null characters")
            try:
                current.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("JSON strings must contain valid Unicode") from error
    return cast(dict[str, object], value)


def pagination(offset: str, limit: str) -> tuple[int, int]:
    start, size = int(offset), int(limit)
    if not 0 <= start <= MAX_OFFSET or not 1 <= size <= 100:
        raise ValueError("pagination requires offset 0..9223372036854775807 and limit 1..100")
    return start, size
