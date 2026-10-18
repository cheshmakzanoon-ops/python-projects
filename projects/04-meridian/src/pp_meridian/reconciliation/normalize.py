"""Stable statement identities, UTC timestamps, and signed amounts."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from pp_meridian.domain.money import parse_amount


def normalize_reference(reference: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", reference.upper())


@dataclass(frozen=True)
class NormalizedRow:
    identity: str
    amount: int
    currency: str
    timestamp: datetime
    reference: str
    payload_hash: str


def normalize_row(row: Mapping[str, object]) -> NormalizedRow:
    identity, currency, date, reference = (
        row.get(k) for k in ("id", "currency", "timestamp", "reference")
    )
    if not all(isinstance(x, str) for x in (identity, currency, date, reference)):
        raise ValueError("row id, currency, timestamp and reference must be strings")
    assert isinstance(identity, str) and isinstance(currency, str)
    assert isinstance(date, str) and isinstance(reference, str)
    if not identity or len(identity) > 200:
        raise ValueError("invalid row identity")
    instant = datetime.fromisoformat(date.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("timestamp needs timezone")
    amount = parse_amount(row.get("amount"), currency)
    if not amount:
        raise ValueError("statement amount must be nonzero")
    if len(reference) > 200:
        raise ValueError("reference too long")
    normalized = normalize_reference(reference)
    try:
        instant = instant.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError("timestamp is outside the supported UTC range") from error
    payload = json.dumps(
        [identity, amount, currency, instant.isoformat(), normalized], separators=(",", ":")
    )
    return NormalizedRow(
        identity,
        amount,
        currency,
        instant,
        normalized,
        hashlib.sha256(payload.encode()).hexdigest(),
    )
