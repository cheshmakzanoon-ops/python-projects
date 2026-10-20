"""Bounded, non-executable JSON interchange for scores and analysis exports."""

import json
import math
import stat
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 4_000_000
MAX_JSON_DEPTH = 64


def read_json(path: Path, max_bytes: int = MAX_JSON_BYTES) -> Any:
    """Read a regular file without trusting its declared size or numeric tokens."""
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("JSON input must be a regular file")
    if metadata.st_size > max_bytes:
        raise ValueError(f"JSON input exceeds {max_bytes} bytes")
    with path.open("rb") as source:
        raw = source.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"JSON input exceeds {max_bytes} bytes")

    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonfinite JSON number is not supported: {value}")

    def validate(value: Any, depth: int = 0) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON input is too deeply nested (maximum {MAX_JSON_DEPTH})")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite JSON numbers are not supported")
        if isinstance(value, (dict, list)):
            children = value.values() if isinstance(value, dict) else value
            for child in children:
                validate(child, depth + 1)

    try:
        result = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
        validate(result)
        return result
    except RecursionError as error:
        raise ValueError("JSON input is too deeply nested") from error
