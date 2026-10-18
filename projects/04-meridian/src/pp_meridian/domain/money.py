"""Exact bounded minor units; negative allocation mirrors positive allocation."""

import re

EXPONENTS = {"USD": 2, "CAD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
MAX_AMOUNT = 10**15


def parse_amount(value: object, currency: str) -> int:
    if currency not in EXPONENTS:
        raise ValueError("unsupported currency")
    if not isinstance(value, str) or not re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?", value):
        raise ValueError("amount must be a canonical decimal string")
    places = EXPONENTS[currency]
    integral, _, fraction = value.removeprefix("-").partition(".")
    if len(fraction) > places:
        raise ValueError("excessive precision")
    result = int(integral) * 10**places + int(fraction.ljust(places, "0") or "0")
    result *= -1 if value.startswith("-") else 1
    if abs(result) > MAX_AMOUNT:
        raise ValueError("amount overflow")
    return int(result)


def allocate(total: int, weights: tuple[int, ...]) -> tuple[int, ...]:
    if type(total) is not int or abs(total) > MAX_AMOUNT:
        raise ValueError("invalid total")
    if not weights or any(type(w) is not int or w < 0 for w in weights) or not sum(weights):
        raise ValueError("weights must be nonnegative integers with positive sum")
    denominator = sum(weights)
    quotients = [abs(total) * weight // denominator for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(abs(total) * weights[i] % denominator), i))
    for i in order[: abs(total) - sum(quotients)]:
        quotients[i] += 1
    return tuple(q if total >= 0 else -q for q in quotients)
