from __future__ import annotations

import math
from pathlib import Path

import pytest

from pp_strata.codec.records import Record
from pp_strata.memtable import Memtable
from pp_strata.sstable import Table, create_table


@pytest.mark.parametrize("cache_blocks", [0, 32])
def test_old_snapshot_point_lookup_skips_blocks_of_newer_hot_key_versions(
    tmp_path: Path, cache_blocks: int
) -> None:
    count = 20000
    records = [Record(b"hot", sequence, bytes(128)) for sequence in range(count, 0, -1)]
    path = tmp_path / "hot.sst"
    create_table(path, records)
    table = Table(path, cache_blocks=cache_blocks)
    try:
        assert len(table.blocks) > 32
        for sequence in (1, 2, count // 2, count - 1, count, 0):
            before = table.block_reads
            expected = Record(b"hot", sequence, bytes(128)) if sequence else None
            assert table.get(b"hot", sequence) == expected
            assert table.block_reads - before <= math.ceil(math.log2(len(table.blocks))) + 2
        table.cache.clear()
        before = table.block_reads
        assert table.get(b"hot", count) == records[0]
        assert table.block_reads - before == 1
    finally:
        table.close()


def test_compound_memtable_seek_matches_all_hot_key_versions() -> None:
    memtable = Memtable()
    for sequence in range(1, 10001):
        memtable.add(
            Record(b"hot", sequence, None if sequence % 7 == 0 else str(sequence).encode())
        )
    memtable.add(Record(b"after", 1, b"adjacent"))
    for sequence in range(10001):
        expected = (
            None
            if sequence == 0
            else Record(b"hot", sequence, None if sequence % 7 == 0 else str(sequence).encode())
        )
        assert memtable.get(b"hot", sequence) == expected
    assert memtable.get(b"between", 5000) is None
