"""A frame is MAGIC, size, CRC32, and a complete record batch."""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

from pp_strata.codec.records import MAX_BATCH, Record, decode, encode
from pp_strata.errors import Corruption
from pp_strata.io import Failpoint, frame, noop, sync_directory, write_all

MAGIC = b"STW1"
HEADER = struct.Struct(">4sII")


class WAL:
    def __init__(self, path: Path, failpoint: Failpoint = noop) -> None:
        self.path = path
        self.failpoint = failpoint
        self.fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            sync_directory(path.parent)
        except BaseException:
            # The caller cannot own or close this instance until construction
            # returns; retain responsibility for the descriptor on this path.
            os.close(self.fd)
            raise

    def recover(self) -> list[list[Record]]:
        """Truncate only an incomplete final frame; complete corrupt frames fail closed."""
        batches: list[list[Record]] = []
        offset = 0
        size = os.fstat(self.fd).st_size
        last_sequence = 0
        while offset < size:
            header = os.pread(self.fd, HEADER.size, offset)
            if len(header) < HEADER.size:
                if not MAGIC.startswith(header[:4]):
                    raise Corruption("invalid partial WAL frame magic")
                break
            magic, length, checksum = HEADER.unpack(header)
            if magic != MAGIC or length > MAX_BATCH or length == 0:
                raise Corruption(f"invalid WAL header at {offset}")
            payload = os.pread(self.fd, length, offset + HEADER.size)
            if len(payload) < length:
                remainder = header + payload
                position = remainder.find(MAGIC, HEADER.size)
                while position >= 0:
                    if len(remainder) - position >= HEADER.size:
                        _, n, crc = HEADER.unpack_from(remainder, position)
                        candidate = remainder[position + HEADER.size : position + HEADER.size + n]
                        if n <= MAX_BATCH and len(candidate) == n and zlib.crc32(candidate) == crc:
                            raise Corruption("interior WAL length hides a later complete frame")
                    position = remainder.find(MAGIC, position + 1)
                break
            if zlib.crc32(payload) != checksum:
                raise Corruption(f"WAL checksum mismatch at {offset}")
            records = decode(payload)
            if not records or len({r.sequence for r in records}) != 1:
                raise Corruption("WAL frame must contain one complete transaction")
            sequence = records[0].sequence
            if sequence <= last_sequence or len({r.key for r in records}) != len(records):
                raise Corruption("non-monotonic WAL sequence or duplicate key")
            last_sequence = sequence
            batches.append(records)
            offset += HEADER.size + length
        if offset < size:
            os.ftruncate(self.fd, offset)
            os.fsync(self.fd)
        os.lseek(self.fd, 0, os.SEEK_END)
        return batches

    def append(self, records: list[Record], sync: bool) -> int:
        payload = encode(records)
        data = MAGIC + frame(payload)
        self.failpoint("before_wal_append")
        write_all(self.fd, data)
        self.failpoint("after_wal_append")
        if sync:
            os.fsync(self.fd)
        self.failpoint("after_wal_sync")
        return len(data)

    def rotate(self) -> None:
        temporary = self.path.with_suffix(".pending")
        fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fsync(fd)
            os.replace(temporary, self.path)
            sync_directory(self.path.parent)
        except BaseException:
            os.close(fd)
            raise
        # Retain the replacement's writable descriptor. Reopening after closing
        # the old WAL could fail and leave the owner holding a stale descriptor.
        previous, self.fd = self.fd, fd
        os.close(previous)

    def close(self) -> None:
        os.close(self.fd)
