"""Checksummed immutable files; fsync precedes publication."""

from __future__ import annotations

import os
from pathlib import Path

from pp_quarry.sources import file_hash


def persist(path: Path) -> tuple[str, int]:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return file_hash(path), path.stat().st_size


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
