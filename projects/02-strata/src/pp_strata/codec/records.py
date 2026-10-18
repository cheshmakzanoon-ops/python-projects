"""Binary records: sequence:u64, kind:u8, key length:u16, value length:u32."""

from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass

from pp_strata.errors import Corruption

MAX_KEY = 4096
MAX_VALUE = 1024 * 1024
MAX_BATCH = 16 * 1024 * 1024
HEADER = struct.Struct(">Q B H I")


@dataclass(frozen=True, slots=True)
class Record:
    key: bytes
    sequence: int
    value: bytes | None

    @property
    def order(self) -> tuple[bytes, int]:
        return self.key, -self.sequence


def validate(key: bytes, value: bytes | None = None) -> None:
    if not isinstance(key, bytes) or (value is not None and not isinstance(value, bytes)):
        raise TypeError("keys and values must be bytes")
    if len(key) > MAX_KEY:
        raise ValueError("key exceeds 4096 bytes")
    if value is not None and len(value) > MAX_VALUE:
        raise ValueError("value exceeds 1 MiB")


def encode(records: Iterable[Record]) -> bytes:
    result = bytearray()
    for record in records:
        validate(record.key, record.value)
        value = record.value or b""
        result.extend(
            HEADER.pack(record.sequence, int(record.value is not None), len(record.key), len(value))
        )
        result.extend(record.key)
        result.extend(value)
        if len(result) > MAX_BATCH:
            raise ValueError("encoded batch exceeds 16 MiB")
    return bytes(result)


def decode(data: bytes) -> list[Record]:
    if len(data) > MAX_BATCH:
        raise Corruption("oversize encoded record batch")
    view = memoryview(data)
    result: list[Record] = []
    offset = 0
    while offset < len(view):
        if len(view) - offset < HEADER.size:
            raise Corruption("truncated record header")
        sequence, kind, key_size, value_size = HEADER.unpack_from(view, offset)
        offset += HEADER.size
        if kind not in (0, 1) or key_size > MAX_KEY or value_size > MAX_VALUE:
            raise Corruption("invalid record type or bounded length")
        if kind == 0 and value_size:
            raise Corruption("tombstone has a value")
        end = offset + key_size + value_size
        if end > len(view) or sequence == 0:
            raise Corruption("truncated record body or invalid sequence")
        key = bytes(view[offset : offset + key_size])
        offset += key_size
        value = bytes(view[offset:end]) if kind else None
        result.append(Record(key, sequence, value))
        offset = end
    return result
