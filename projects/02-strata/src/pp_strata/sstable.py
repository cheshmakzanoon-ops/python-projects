"""Immutable checksummed blocks, a sparse range index, and persistent Bloom filters."""

from __future__ import annotations

import bisect
import hashlib
import json
import os
import struct
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from pp_strata.codec.records import MAX_BATCH, Record, decode, encode
from pp_strata.errors import Corruption
from pp_strata.io import Failpoint, frame, noop, sync_directory, unframe, write_all

MAGIC = b"STRATAS1"
END = b"STEND001"
TRAILER = struct.Struct(">Q8s")
BLOCK_TARGET = 64 * 1024


def hashes(key: bytes) -> tuple[int, int]:
    """Stable BLAKE2b-128, big endian halves; no process-random hash()."""
    digest = hashlib.blake2b(key, digest_size=16, person=b"strata-bloom-v1").digest()
    return int.from_bytes(digest[:8]), int.from_bytes(digest[8:]) | 1


class Bloom:
    def __init__(self, data: bytes) -> None:
        if len(data) < 8 or len(data) > MAX_BATCH:
            raise Corruption("invalid Bloom size")
        self.data = bytearray(data)

    @classmethod
    def build(cls, keys: list[bytes]) -> Bloom:
        bloom = cls(bytes(max(8, (len(keys) * 10 + 7) // 8)))
        for key in keys:
            first, delta = hashes(key)
            for i in range(7):
                bit = (first + i * delta) % (len(bloom.data) * 8)
                bloom.data[bit // 8] |= 1 << (bit % 8)
        return bloom

    def contains(self, key: bytes) -> bool:
        first, delta = hashes(key)
        for i in range(7):
            bit = (first + i * delta) % (len(self.data) * 8)
            if not self.data[bit // 8] & (1 << (bit % 8)):
                return False
        return True


@dataclass(frozen=True, slots=True)
class Block:
    offset: int
    length: int
    first: bytes
    last: bytes


def create_table(path: Path, records: Iterable[Record], failpoint: Failpoint = noop) -> None:
    """Create exclusively; publish only after both file and directory synchronization."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        write_all(fd, MAGIC)
        failpoint("table_created")
        offset = len(MAGIC)
        blocks: list[list[object]] = []
        pending: list[Record] = []
        pending_size = 0
        keys: list[bytes] = []
        previous: tuple[bytes, int] | None = None

        def emit() -> None:
            nonlocal offset, pending_size
            if not pending:
                return
            data = frame(encode(pending))
            blocks.append([offset, len(data), pending[0].key.hex(), pending[-1].key.hex()])
            write_all(fd, data)
            offset += len(data)
            pending.clear()
            pending_size = 0

        for record in records:
            if previous is not None and record.order <= previous:
                raise ValueError("SSTable input must be strictly sorted")
            if pending_size + len(record.key) + len(record.value or b"") + 15 > BLOCK_TARGET:
                emit()
            if not keys or keys[-1] != record.key:
                keys.append(record.key)
            pending.append(record)
            pending_size += len(record.key) + len(record.value or b"") + 15
            previous = record.order
        emit()
        bloom = Bloom.build(keys)
        metadata = json.dumps(
            {"blocks": blocks, "bloom": bytes(bloom.data).hex()}, separators=(",", ":")
        ).encode()
        if len(metadata) > MAX_BATCH:
            raise ValueError("SSTable index exceeds format limit; reduce flush size")
        write_all(fd, frame(metadata))
        write_all(fd, TRAILER.pack(offset, END))
        os.fsync(fd)
        failpoint("table_synced")
    finally:
        os.close(fd)
    sync_directory(path.parent)


class Table:
    def __init__(self, path: Path, cache_blocks: int = 32) -> None:
        self.path = path
        self.fd = os.open(path, os.O_RDONLY)
        self.cache_blocks = cache_blocks
        self.cache: OrderedDict[int, list[Record]] = OrderedDict()
        self.read_bytes = 0
        self.block_reads = 0
        self.cache_hits = 0
        try:
            size = os.fstat(self.fd).st_size
            if size < len(MAGIC) + TRAILER.size + 8 or os.pread(self.fd, 8, 0) != MAGIC:
                raise Corruption("unsupported or truncated SSTable")
            index_offset, end = TRAILER.unpack(os.pread(self.fd, TRAILER.size, size - TRAILER.size))
            index_size = size - TRAILER.size - index_offset
            if end != END or index_offset < len(MAGIC) or not 8 <= index_size <= MAX_BATCH + 8:
                raise Corruption("invalid SSTable footer bounds")
            raw: object = json.loads(
                unframe(os.pread(self.fd, index_size, index_offset), MAX_BATCH)
            )
            if (
                not isinstance(raw, dict)
                or not isinstance(raw.get("blocks"), list)
                or not isinstance(raw.get("bloom"), str)
            ):
                raise Corruption("invalid SSTable index schema")
            self.bloom = Bloom(bytes.fromhex(raw["bloom"]))
            self.blocks: list[Block] = []
            expected_offset = len(MAGIC)
            last_key = b""
            for entry in raw["blocks"]:
                if not isinstance(entry, list) or len(entry) != 4:
                    raise Corruption("invalid block entry")
                offset, length, first, last = entry
                if (
                    not isinstance(offset, int)
                    or not isinstance(length, int)
                    or not isinstance(first, str)
                    or not isinstance(last, str)
                ):
                    raise Corruption("invalid block entry types")
                a, b = bytes.fromhex(first), bytes.fromhex(last)
                if (
                    offset != expected_offset
                    or not 8 < length <= MAX_BATCH + 8
                    or offset + length > index_offset
                    or a > b
                    or a < last_key
                ):
                    raise Corruption("invalid block range")
                self.blocks.append(Block(offset, length, a, b))
                expected_offset += length
                last_key = b
            if expected_offset != index_offset:
                raise Corruption("SSTable index does not cover data")
            self.first_keys = [block.first for block in self.blocks]
            self.last_keys = [block.last for block in self.blocks]
        except (ValueError, UnicodeError, KeyError, TypeError, struct.error) as exc:
            os.close(self.fd)
            raise Corruption("invalid SSTable metadata") from exc
        except BaseException:
            os.close(self.fd)
            raise

    def _block(self, index: int) -> list[Record]:
        if index in self.cache:
            self.cache_hits += 1
            self.cache.move_to_end(index)
            return self.cache[index]
        block = self.blocks[index]
        data = os.pread(self.fd, block.length, block.offset)
        self.read_bytes += len(data)
        self.block_reads += 1
        records = decode(unframe(data, MAX_BATCH))
        if not records or records[0].key != block.first or records[-1].key != block.last:
            raise Corruption("SSTable block range disagrees with index")
        if any(a.order >= b.order for a, b in zip(records, records[1:])):
            raise Corruption("SSTable records out of order")
        if self.cache_blocks:
            self.cache[index] = records
            while len(self.cache) > self.cache_blocks:
                self.cache.popitem(last=False)
        return records

    def records(self, start: bytes = b"", stop: bytes | None = None) -> Iterator[Record]:
        index = max(0, bisect.bisect_right(self.first_keys, start) - 1)
        while index > 0 and self.blocks[index - 1].last >= start:
            index -= 1
        previous: tuple[bytes, int] | None = None
        for i in range(index, len(self.blocks)):
            if stop is not None and self.blocks[i].first >= stop:
                return
            for record in self._block(i):
                if previous is not None and record.order <= previous:
                    raise Corruption("SSTable blocks not globally ordered")
                previous = record.order
                if record.key >= start and (stop is None or record.key < stop):
                    yield record

    def get(self, key: bytes, sequence: int) -> Record | None:
        if not self.bloom.contains(key):
            return None
        # Block key ranges first bound the search. Within a long hot-key run,
        # terminal internal keys let us skip blocks of newer invisible versions.
        first = bisect.bisect_left(self.last_keys, key)
        stop = bisect.bisect_right(self.first_keys, key)
        target = key, -sequence
        if first >= stop:
            return None
        # The usual latest-version lookup still needs only its first block.
        leading = self._block(first)
        index = bisect.bisect_left(leading, target, key=lambda record: record.order)
        if index < len(leading):
            return leading[index] if leading[index].key == key else None
        low, high = first + 1, stop
        while low < high:
            middle = (low + high) // 2
            if self._block(middle)[-1].order < target:
                low = middle + 1
            else:
                high = middle
        if low < stop:
            records = self._block(low)
            index = bisect.bisect_left(records, target, key=lambda record: record.order)
            if index < len(records) and records[index].key == key:
                return records[index]
        return None

    def close(self) -> None:
        os.close(self.fd)
        self.cache.clear()
