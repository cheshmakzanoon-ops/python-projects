from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import pytest

from pp_strata.codec.records import MAX_BATCH, MAX_VALUE, Record, decode, encode
from pp_strata.errors import Corruption
from pp_strata.io import durable_mkdir, frame, read_metadata, sync_directory, unframe
from pp_strata.memtable import Memtable
from pp_strata.sstable import Bloom, Table, create_table, hashes
from pp_strata.wal.frames import HEADER, WAL


def test_record_fixed_vector() -> None:
    record = Record(b"k", 1, b"v")
    assert encode([record]).hex() == "0000000000000001010001000000016b76"
    assert decode(bytes.fromhex("0000000000000001000001000000006b")) == [Record(b"k", 1, None)]
    assert decode(encode([record, Record(b"", 2, b"")])) == [record, Record(b"", 2, b"")]


def test_stable_hash_vector() -> None:
    # Frozen BLAKE2b reference digest: 63c243d03d7ad2f44ad7db39c8db3dcf.
    assert hashes(b"catalog:0001") == (7188382516900451060, 5393020120028888527)
    digest = hashlib.blake2b(b"catalog:0001", digest_size=16, person=b"strata-bloom-v1").digest()
    assert hashes(b"catalog:0001") == (int.from_bytes(digest[:8]), int.from_bytes(digest[8:]) | 1)


@pytest.mark.parametrize(
    "data",
    [
        b"x",
        bytes(15),
        struct.pack(">QBHI", 1, 2, 0, 0),
        struct.pack(">QBHI", 1, 0, 0, 1) + b"v",
        struct.pack(">QBHI", 1, 1, 4097, 0),
        struct.pack(">QBHI", 1, 1, 0, MAX_VALUE + 1),
        struct.pack(">QBHI", 1, 1, 1, 0),
    ],
)
def test_bounded_malformed_records(data: bytes) -> None:
    with pytest.raises(Corruption):
        decode(data)


def test_limits_and_checksum() -> None:
    with pytest.raises(TypeError):
        encode([Record("bad", 1, b"v")])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        encode([Record(b"k", 1, b"x" * (MAX_VALUE + 1))])
    with pytest.raises(ValueError):
        encode([Record(str(i).encode(), 1, bytes(MAX_VALUE)) for i in range(17)])
    with pytest.raises(Corruption):
        decode(bytes(MAX_BATCH + 1))
    for bad in (
        b"",
        frame(b"x")[:-1],
        frame(b"x")[:-1] + b"y",
        struct.pack(">II", MAX_BATCH + 1, 0),
    ):
        with pytest.raises(Corruption):
            unframe(bad, MAX_BATCH)


def test_skiplist_order_and_snapshot_lookup() -> None:
    mem = Memtable()
    records = [
        Record(b"b", 2, b"2"),
        Record(b"a", 3, None),
        Record(b"a", 1, b"1"),
        Record(b"a", 2, b"2"),
        Record(b"", 4, b"empty"),
    ]
    for record in records:
        mem.add(record)
    assert list(mem.records()) == sorted(records, key=lambda r: (r.key, -r.sequence))
    assert mem.get(b"a", 1) == Record(b"a", 1, b"1")
    assert mem.get(b"a", 0) is None
    assert mem.get(b"missing", 5) is None
    assert list(mem.records(b"a", b"b")) == sorted(records[1:4], key=lambda r: -r.sequence)


def test_bloom_no_false_negatives() -> None:
    keys = [str(i).encode() for i in range(1000)]
    bloom = Bloom.build(keys)
    assert all(bloom.contains(key) for key in keys)
    assert sum(bloom.contains(f"missing:{i}".encode()) for i in range(1000)) < 100
    with pytest.raises(Corruption):
        Bloom(b"short")


def test_table_multiblock_hot_key(tmp_path: Path) -> None:
    path = tmp_path / "test.sst"
    records = [Record(b"a", i, bytes(3000)) for i in range(80, 0, -1)] + [Record(b"z", 1, b"last")]
    create_table(path, iter(records))
    table = Table(path, cache_blocks=1)
    try:
        assert len(table.blocks) > 2
        assert table.get(b"a", 1) == Record(b"a", 1, bytes(3000))
        assert table.get(b"a", 0) is None
        assert table.get(b"absent", 99) is None
        assert list(table.records()) == records
        assert list(table.records(b"z", b"zz")) == records[-1:]
        assert list(table.records(b"z", b"z")) == []
        assert len(table.cache) == 1
    finally:
        table.close()


@pytest.mark.parametrize("location", ["header", "data", "footer", "index"])
def test_table_corruption(tmp_path: Path, location: str) -> None:
    path = tmp_path / "test.sst"
    create_table(path, iter([Record(b"k", 1, b"v")]))
    data = bytearray(path.read_bytes())
    offset = {"header": 0, "data": 16, "footer": len(data) - 1, "index": 45}[location]
    data[offset] ^= 1
    path.write_bytes(data)
    with pytest.raises(Corruption):
        table = Table(path)
        try:
            list(table.records())
        finally:
            table.close()


def test_table_unsorted_and_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_table(tmp_path / "bad", iter([Record(b"b", 1, b"v"), Record(b"a", 1, b"v")]))
    create_table(tmp_path / "empty", iter([]))
    table = Table(tmp_path / "empty", 0)
    assert list(table.records()) == []
    table.close()


def test_wal_tail_and_interior_corruption(tmp_path: Path) -> None:
    path = tmp_path / "WAL"
    wal = WAL(path)
    wal.append([Record(b"a", 1, b"one")], True)
    first_size = path.stat().st_size
    wal.append([Record(b"b", 2, b"two")], True)
    wal.close()
    original = path.read_bytes()
    for cut in range(1, len(original) - first_size):
        path.write_bytes(original[:-cut])
        wal = WAL(path)
        assert wal.recover() == [[Record(b"a", 1, b"one")]]
        wal.close()
        assert path.stat().st_size == first_size
    broken = bytearray(original)
    broken[HEADER.size] ^= 1
    path.write_bytes(broken)
    wal = WAL(path)
    with pytest.raises(Corruption):
        wal.recover()
    wal.close()
    broken = bytearray(original)
    struct.pack_into(">I", broken, 4, 10000)
    path.write_bytes(broken)
    wal = WAL(path)
    with pytest.raises(Corruption, match="later complete"):
        wal.recover()
    wal.close()


def test_manifest_rejects_non_format(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST"
    path.write_bytes(b"not strata")
    with pytest.raises(Corruption):
        read_metadata(path)
    path.write_bytes(b"STRATAM1" + frame(b"[]"))
    with pytest.raises(Corruption):
        read_metadata(path)


def test_wal_invalid_header_and_sequence(tmp_path: Path) -> None:
    for data in (
        b"bad!",
        b"STW1" + struct.pack(">II", MAX_BATCH + 1, 0),
        b"STW1" + frame(encode([Record(b"a", 1, b"1"), Record(b"b", 2, b"2")])),
    ):
        path = tmp_path / "WAL"
        path.write_bytes(data)
        wal = WAL(path)
        with pytest.raises(Corruption):
            wal.recover()
        wal.close()
    path.write_bytes(b"")
    wal = WAL(path)
    wal.append([Record(b"a", 2, b"a")], False)
    wal.append([Record(b"b", 1, b"b")], False)
    with pytest.raises(Corruption):
        wal.recover()
    wal.close()


def test_table_rejects_truncated_file(tmp_path: Path) -> None:
    path = tmp_path / "table"
    path.write_bytes(b"STRATAS1")
    with pytest.raises(Corruption):
        Table(path)
    os.unlink(path)


def test_new_directory_entries_synced_from_existing_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []

    def record_sync(path: Path) -> None:
        synced.append(path)
        sync_directory(path)

    monkeypatch.setattr("pp_strata.io.sync_directory", record_sync)
    durable_mkdir(tmp_path / "new-parent" / "nested" / "database")
    assert synced == [tmp_path, tmp_path / "new-parent", tmp_path / "new-parent" / "nested"]
    assert (tmp_path / "new-parent" / "nested" / "database").is_dir()
    with pytest.raises(FileExistsError):
        durable_mkdir(tmp_path / "new-parent", exist_ok=False)
