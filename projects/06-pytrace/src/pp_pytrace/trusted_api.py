"""Trusted migration fixture API version 1; synthetic, never a target plugin."""

from __future__ import annotations

__version__ = "1"
_UNSET = object()


def deliver(
    payload: str, *, timeout: object = _UNSET, deadline: object = _UNSET
) -> tuple[str, int]:
    """Old timeout and new deadline are equivalent keyword-only spellings."""
    if timeout is not _UNSET and deadline is not _UNSET:
        raise TypeError("specify one deadline spelling")
    value = deadline if deadline is not _UNSET else timeout
    if value is _UNSET:
        value = 10
    if not isinstance(payload, str) or not isinstance(value, int) or value < 0:
        raise ValueError("payload must be text and deadline a nonnegative integer")
    return payload, value
