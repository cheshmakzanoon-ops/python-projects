from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pp_quarry import Config, Lakehouse


@pytest.fixture
def lake(tmp_path: Path) -> Any:
    with Lakehouse(
        tmp_path / "lake", Config(buckets=2, batch_size=8, max_record_bytes=4096)
    ) as value:
        yield value


def event(
    key: str = "x",
    version: int = 1,
    value: int = 3,
    *,
    day: str = "2026-01-01",
    operation: str = "upsert",
    **extra: object,
) -> dict[str, Any]:
    return {
        "source_namespace": "devices",
        "key": key,
        "version": version,
        "operation": operation,
        "payload": {"device": key, "day": day, "value": value, **extra}
        if operation == "upsert"
        else {},
    }


def source(tmp_path: Path, rows: list[dict[str, Any]], name: str = "input.ndjson") -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    return path
