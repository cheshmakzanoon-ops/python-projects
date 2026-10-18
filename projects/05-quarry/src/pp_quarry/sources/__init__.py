"""Bounded immutable NDJSON/CSV sources. CSV records occupy one physical line."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path

from pp_quarry.model.events import JSON, Event


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _lines(
    path: Path, limit: int, observe: Callable[[bytes], object] | None
) -> Iterator[tuple[int, bytes]]:
    with path.open("rb") as stream:
        offset = 0
        while line := stream.readline(limit + 1):
            offset += len(line)
            if len(line) > limit:
                raise ValueError("source record/header exceeds memory limit")
            if observe is not None:
                observe(line)
            yield offset, line


def _csv_row(line: bytes) -> list[str]:
    try:
        return next(csv.reader([line.decode("utf-8")], strict=True))
    except csv.Error as exc:
        raise ValueError(
            "CSV requires one complete record per physical line; multiline quoted records are unsupported"
        ) from exc


def read(
    path: Path,
    max_record_bytes: int = 1024 * 1024,
    *,
    observe: Callable[[bytes], object] | None = None,
) -> Iterator[tuple[int, Event]]:
    lines = _lines(path, max_record_bytes, observe)
    if path.suffix == ".csv":
        csv.field_size_limit(max_record_bytes)
        first = next(lines, None)
        if first is None:
            return
        header = _csv_row(first[1])
        allowed = {"source_namespace", "namespace", "key", "version", "operation", "payload"}
        if (
            len(header) != len(set(header))
            or set(header) - allowed
            or not {"key", "version", "operation", "payload"} <= set(header)
        ):
            raise ValueError("CSV header must contain unique declared event columns")
        for ordinal, (_, line) in enumerate(lines, 1):
            fields = _csv_row(line)
            if len(fields) != len(header):
                raise ValueError("CSV record does not match header width")
            row = dict(zip(header, fields, strict=True))
            raw: dict[str, JSON] = dict(row)
            raw["version"] = int(row["version"])
            raw["payload"] = json.loads(row["payload"])
            yield ordinal, Event.from_dict(raw)
    else:
        for offset, line in lines:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("event must be an object")
            yield offset, Event.from_dict(value)
