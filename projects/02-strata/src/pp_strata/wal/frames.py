"""Versioned WAL framing and read-only recovery planning before tail repair."""

from __future__ import annotations

import os
import stat
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from pp_strata.codec.records import MAX_BATCH, Record, decode, encode
from pp_strata.errors import Corruption
from pp_strata.io import Failpoint, noop, sync_directory, write_all

LEGACY_MAGIC = b"STW1"
LEGACY_HEADER = struct.Struct(">4sII")
MAGIC = b"STW2"
HEADER = struct.Struct(">4sIII")
FileSignature = tuple[int, int, int, int, int]


def _signature(fd: int) -> FileSignature:
    metadata = os.fstat(fd)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """A validated physical prefix; constructing a plan never changes a file."""

    signature: FileSignature
    valid_bytes: int
    batches: tuple[tuple[Record, ...], ...]

    @property
    def discarded_bytes(self) -> int:
        return self.signature[2] - self.valid_bytes

    def replay_after(self, checkpoint: int) -> tuple[tuple[Record, ...], ...]:
        selected = tuple(batch for batch in self.batches if batch[0].sequence > checkpoint)
        for expected, batch in enumerate(selected, start=checkpoint + 1):
            if batch[0].sequence != expected:
                raise Corruption("WAL sequence gap after manifest checkpoint")
        return selected


def _legacy_tail_hides_frame(data: bytes) -> bool:
    """Fail closed for ambiguous v1 lengths; v2 never scans opaque user bytes."""
    for magic, structure in ((LEGACY_MAGIC, LEGACY_HEADER), (MAGIC, HEADER)):
        position = data.find(magic, LEGACY_HEADER.size)
        while position >= 0:
            if len(data) - position >= structure.size:
                header = data[position : position + structure.size]
                _, length, checksum, *_ = structure.unpack(header)
                protected = magic != MAGIC or zlib.crc32(header[:-4]) == HEADER.unpack(header)[3]
                payload = data[position + structure.size : position + structure.size + length]
                if protected and 0 < length <= MAX_BATCH and len(payload) == length:
                    if zlib.crc32(payload) == checksum:
                        try:
                            records = decode(payload)
                        except Corruption:
                            pass
                        else:
                            if records and len({record.sequence for record in records}) == 1:
                                return True
            position = data.find(magic, position + 1)
    return False


class WAL:
    def __init__(self, path: Path, failpoint: Failpoint = noop, *, create: bool = True) -> None:
        self.path = path
        self.failpoint = failpoint
        flags = os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW
        if create:
            flags |= os.O_CREAT
        self.fd = os.open(path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(self.fd).st_mode):
                raise Corruption("WAL must be a regular file")
            if create:
                os.fsync(self.fd)
            sync_directory(path.parent)
        except BaseException:
            # The caller cannot own or close this instance until construction
            # returns; retain responsibility for the descriptor on this path.
            os.close(self.fd)
            raise

    def scan(self) -> RecoveryPlan:
        """Validate without seeking, truncating, or publishing any recovered record.

        V2 protects length and payload checksum with an independent header CRC,
        so a torn payload cannot be confused with frame-shaped arbitrary values.
        V1 lacks that information and retains its conservative ambiguity refusal.
        """
        signature = _signature(self.fd)
        size = signature[2]
        batches: list[tuple[Record, ...]] = []
        offset, last_sequence = 0, 0
        while offset < size:
            magic = os.pread(self.fd, 4, offset)
            if len(magic) < 4:
                if not any(candidate.startswith(magic) for candidate in (MAGIC, LEGACY_MAGIC)):
                    raise Corruption("invalid partial WAL frame magic")
                break
            if magic == MAGIC:
                structure = HEADER
            elif magic == LEGACY_MAGIC:
                structure = LEGACY_HEADER
            else:
                raise Corruption(f"invalid WAL magic at {offset}")
            header = os.pread(self.fd, structure.size, offset)
            if len(header) < structure.size:
                break
            _, length, checksum, *protection = structure.unpack(header)
            if protection and zlib.crc32(header[:-4]) != protection[0]:
                raise Corruption(f"WAL header checksum mismatch at {offset}")
            if not 0 < length <= MAX_BATCH:
                raise Corruption(f"invalid WAL header at {offset}")
            payload = os.pread(self.fd, length, offset + structure.size)
            if len(payload) < length:
                if magic == LEGACY_MAGIC and _legacy_tail_hides_frame(header + payload):
                    raise Corruption("interior WAL length hides a later complete frame")
                break
            if zlib.crc32(payload) != checksum:
                raise Corruption(f"WAL checksum mismatch at {offset}")
            records = decode(payload)
            if not records or len({record.sequence for record in records}) != 1:
                raise Corruption("WAL frame must contain one complete transaction")
            sequence = records[0].sequence
            if sequence <= last_sequence or len({record.key for record in records}) != len(records):
                raise Corruption("non-monotonic WAL sequence or duplicate key")
            if last_sequence and sequence != last_sequence + 1:
                raise Corruption("WAL sequence gap between complete frames")
            last_sequence = sequence
            batches.append(tuple(records))
            offset += structure.size + length
        if _signature(self.fd) != signature:
            raise Corruption("WAL changed during recovery planning")
        return RecoveryPlan(signature, offset, tuple(batches))

    def apply_recovery(self, plan: RecoveryPlan) -> None:
        """Repair only after logical replay validation accepts the physical plan."""
        if _signature(self.fd) != plan.signature:
            raise Corruption("WAL changed after recovery planning")
        if plan.discarded_bytes:
            os.ftruncate(self.fd, plan.valid_bytes)
            os.fsync(self.fd)
        os.lseek(self.fd, 0, os.SEEK_END)

    def recover(self) -> list[list[Record]]:
        """Standalone physical recovery; Database also validates its checkpoint."""
        plan = self.scan()
        self.apply_recovery(plan)
        return [list(batch) for batch in plan.batches]

    def append(self, records: list[Record], sync: bool) -> int:
        payload = encode(records)
        prefix = LEGACY_HEADER.pack(MAGIC, len(payload), zlib.crc32(payload))
        data = prefix + struct.pack(">I", zlib.crc32(prefix)) + payload
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
