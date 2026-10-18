"""POSIX persistence primitives; verification is never bypassed."""

from __future__ import annotations

import json
import os
import struct
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from pp_strata.errors import Corruption

Failpoint: TypeAlias = Callable[[str], None]
FRAME = struct.Struct(">II")


def noop(name: str) -> None:
    pass


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("zero-length write")
        view = view[written:]


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_mkdir(path: Path, *, exist_ok: bool = True) -> None:
    """Persist every newly created directory entry, from the existing ancestor down."""
    missing: list[Path] = []
    ancestor = path
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    path.mkdir(parents=True, exist_ok=exist_ok)
    for created in reversed(missing):
        sync_directory(created.parent)


def frame(data: bytes) -> bytes:
    return FRAME.pack(len(data), zlib.crc32(data)) + data


def unframe(data: bytes, limit: int) -> bytes:
    if len(data) < FRAME.size:
        raise Corruption("truncated checksum frame")
    size, checksum = FRAME.unpack_from(data)
    if size > limit or len(data) != FRAME.size + size:
        raise Corruption("invalid bounded frame length")
    payload = data[FRAME.size :]
    if zlib.crc32(payload) != checksum:
        raise Corruption("checksum mismatch")
    return payload


def atomic_metadata(path: Path, value: dict[str, object], failpoint: Failpoint = noop) -> None:
    data = b"STRATAM1" + frame(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    temporary = path.with_suffix(".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    failpoint("before_manifest_replace")
    os.replace(temporary, path)
    failpoint("after_manifest_replace")
    sync_directory(path.parent)
    failpoint("after_manifest_sync")


def read_metadata(path: Path) -> dict[str, object]:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise Corruption("oversize manifest")
    data = path.read_bytes()
    if not data.startswith(b"STRATAM1"):
        raise Corruption("unsupported manifest format")
    try:
        result: object = json.loads(unframe(data[8:], 64 * 1024 * 1024))
    except (ValueError, UnicodeError) as exc:
        raise Corruption("invalid manifest JSON") from exc
    if not isinstance(result, dict):
        raise Corruption("manifest must be an object")
    return result
