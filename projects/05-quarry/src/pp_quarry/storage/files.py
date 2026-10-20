"""Checksummed immutable files; fsync precedes publication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

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


def manifest_path(root: Path, value: str) -> Path:
    """Format-v1 manifests reference regular files directly in owned data."""
    relative = Path(value)
    path = root / relative
    data = root / "data"
    if (
        relative.is_absolute()
        or len(relative.parts) != 2
        or relative.parts[0] != "data"
        or relative.suffix != ".parquet"
        or any(character in relative.name for character in "*?[]")
        or data.is_symlink()
        or path.is_symlink()
        or path.resolve().parent != data
        or not path.is_file()
    ):
        raise ValueError("manifest path must name a regular file in owned data without symlinks")
    return path


def verify_entry(root: Path, entry: dict[str, Any]) -> Path:
    """Verify committed bytes before reading or reusing a published file.

    The catalog checksum authenticates content relative to the local manifest,
    not its author. The dataset still requires a trusted local filesystem.
    """
    path = manifest_path(root, entry["path"])
    if path.stat().st_size != entry["bytes"] or file_hash(path) != entry["sha256"]:
        raise ValueError(f"checksum/size mismatch: {path.name}")
    parquet = pq.ParquetFile(path)
    try:
        if str(parquet.schema_arrow) != entry["schema"]:
            raise ValueError(f"Parquet schema mismatch: {path.name}")
        if parquet.metadata.num_rows != entry["rows"]:
            raise ValueError(f"row count mismatch: {path.name}")
    finally:
        parquet.close()
    return path
