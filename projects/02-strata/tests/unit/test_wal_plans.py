from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from pp_strata import Corruption, Database
from pp_strata.codec.records import Record, encode
from pp_strata.io import frame
from pp_strata.wal.frames import HEADER, LEGACY_MAGIC, MAGIC, WAL


def test_v2_header_fixed_vector_and_independent_checksums(tmp_path: Path) -> None:
    path = tmp_path / "WAL"
    wal = WAL(path)
    try:
        records = [Record(b"key", 1, b"value")]
        wal.append(records, sync=True)
        raw = path.read_bytes()
        assert raw[:4] == b"STW2"
        magic, length, checksum, header_checksum = struct.unpack(">4sIII", raw[:16])
        assert magic == MAGIC
        assert length == len(encode(records))
        assert checksum == zlib.crc32(raw[16:])
        assert header_checksum == zlib.crc32(raw[:12])
        plan = wal.scan()
        assert plan.batches == (tuple(records),)
        assert plan.discarded_bytes == 0
        assert path.read_bytes() == raw
    finally:
        wal.close()


def test_complete_legacy_log_can_continue_with_v2_and_flush(tmp_path: Path) -> None:
    database = tmp_path / "database"
    with Database.open(database):
        pass
    legacy = LEGACY_MAGIC + frame(encode([Record(b"old", 1, b"v1")]))
    (database / "WAL").write_bytes(legacy)
    with Database.open(database) as db:
        with db.begin() as tx:
            tx.put(b"new", b"v2")
    assert (database / "WAL").read_bytes()[len(legacy) : len(legacy) + 4] == MAGIC
    with Database.open(database) as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"new", b"v2"), (b"old", b"v1")]
        db.flush()
        assert (database / "WAL").read_bytes() == b""
    with Database.open(database) as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"new", b"v2"), (b"old", b"v1")]


def test_legacy_ambiguous_tail_remains_preserved(tmp_path: Path) -> None:
    payload = encode(
        [Record(b"outer", 1, LEGACY_MAGIC + frame(encode([Record(b"inner", 2, b"v")])) + b"end")]
    )
    original = (LEGACY_MAGIC + frame(payload))[:-1]
    path = tmp_path / "WAL"
    path.write_bytes(original)
    wal = WAL(path, create=False)
    try:
        with pytest.raises(Corruption, match="later complete frame"):
            wal.recover()
        assert path.read_bytes() == original
    finally:
        wal.close()


@pytest.mark.parametrize("offset", [4, 8, 12])
def test_v2_header_corruption_never_truncates_later_transactions(
    tmp_path: Path, offset: int
) -> None:
    path = tmp_path / "WAL"
    wal = WAL(path)
    try:
        wal.append([Record(b"first", 1, b"one")], True)
        wal.append([Record(b"second", 2, b"two")], True)
        original = bytearray(path.read_bytes())
        original[offset] ^= 1
        path.write_bytes(original)
        with pytest.raises(Corruption, match="header checksum"):
            wal.recover()
        assert path.read_bytes() == original
    finally:
        wal.close()


def test_recovery_plan_is_read_only_and_cannot_truncate_a_newer_log(tmp_path: Path) -> None:
    path = tmp_path / "WAL"
    wal = WAL(path)
    try:
        wal.append([Record(b"first", 1, b"one")], True)
        complete = path.read_bytes()
        with path.open("ab") as stream:
            stream.write(MAGIC[:2])
        plan = wal.scan()
        assert plan.valid_bytes == len(complete)
        assert plan.discarded_bytes == 2
        assert path.read_bytes() == complete + MAGIC[:2]
        with path.open("ab") as stream:
            stream.write(b"different")
        newer = path.read_bytes()
        with pytest.raises(Corruption, match="changed after"):
            wal.apply_recovery(plan)
        assert path.read_bytes() == newer
    finally:
        wal.close()


@pytest.mark.parametrize("cut", range(1, HEADER.size + 1))
def test_torn_v2_header_or_payload_retains_complete_prefix(tmp_path: Path, cut: int) -> None:
    path = tmp_path / "WAL"
    wal = WAL(path)
    try:
        first = [Record(b"first", 1, b"acknowledged")]
        wal.append(first, True)
        prefix = path.read_bytes()
        wal.append([Record(b"second", 2, b"incomplete")], False)
        original = path.read_bytes()
        path.write_bytes(original[: len(prefix) + cut])
        assert wal.recover() == [first]
        assert path.read_bytes() == prefix
    finally:
        wal.close()
