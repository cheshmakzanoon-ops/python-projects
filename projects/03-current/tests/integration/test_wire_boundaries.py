"""The wire size budget is independent of delimiters and internal ordinals."""

from dataclasses import replace
from pathlib import Path

import pytest

from pp_current import Journal, Record
from pp_current.sources.ndjson import read_ndjson


def maximum_record() -> Record:
    empty = Record("s", 0, 9)
    return replace(empty, payload="x" * (16_384 - len(empty.wire().encode())))


def test_maximum_wire_record_round_trips_through_newline_source(tmp_path: Path) -> None:
    record = maximum_record()
    assert len(record.wire().encode()) == 16_384
    path = tmp_path / "events.ndjson"
    path.write_bytes(record.wire().encode() + b"\n")
    assert list(read_ndjson(path)) == [record]
    path.write_bytes(record.wire().encode() + b" \n")
    with pytest.raises(ValueError, match="overlong"):
        list(read_ndjson(path))


def test_durable_ordinal_does_not_consume_wire_payload_capacity(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "boundary.db")
    try:
        journal.admit([Record("s", 0, offset) for offset in range(9)])
        record = maximum_record()
        admitted = journal.admit([record])[0]
        assert admitted.ingress_ordinal == 10
        assert admitted.wire() == record.wire()
        assert journal.read(9) == [admitted]
        assert journal.admit([record]) == [admitted]
        with pytest.raises(ValueError, match="16 KiB"):
            replace(record, payload=record.payload + "x")
    finally:
        journal.close()
