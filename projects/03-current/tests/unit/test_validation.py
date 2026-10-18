import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from pp_current import Config, Engine, Journal, Record, Runtime, canonical, partition_for
from pp_current.operators.tumbling import windows
from pp_current.sources.ndjson import read_ndjson

INPUT = canonical(["s", 0])


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(source_id=""),
        dict(partition=-1),
        dict(source_offset=-1),
        dict(schema_version=2),
        dict(kind="unknown"),
        dict(stream="unknown"),
        dict(value=1.2),
        dict(payload="x" * 17000),
        dict(key=1),
        dict(partition="x"),
        dict(event_time=2**63),
        dict(event_time="0"),
        dict(event_time=None),
        dict(event_time=True),
        dict(ingress_ordinal=-1),
        dict(source_offset=2**63),
    ],
)
def test_record_boundary_validation(kwargs: dict[str, object]) -> None:
    defaults: dict[str, object] = dict(source_id="s", partition=0, source_offset=0)
    defaults.update(kwargs)
    with pytest.raises(ValueError):
        Record(**defaults)  # type: ignore[arg-type]


def test_configuration_and_operator_failures(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Config(())
    with pytest.raises(ValueError):
        Config((INPUT,), workers=0)
    with pytest.raises(ValueError):
        windows(1, 10, 3)
    with pytest.raises(ValueError):
        partition_for("key", 0)
    engine = Engine(Config((INPUT,), state_limit=1))
    with pytest.raises(MemoryError):
        engine.apply(Record("s", 0, 0, ingress_ordinal=1))
    engine = Engine(Config((INPUT,)))
    with pytest.raises(ValueError, match="contiguous"):
        engine.apply(Record("s", 0, 0, ingress_ordinal=2))
    with pytest.raises(ValueError, match="unknown"):
        engine.apply(Record("other", 0, 0, ingress_ordinal=1))
    engine.apply(Record("s", 0, 0, kind="idle", ingress_ordinal=1))
    with pytest.raises(ValueError, match="resume"):
        engine.apply(Record("s", 0, 1, ingress_ordinal=2))
    journal = Journal(tmp_path / "j.db")
    with pytest.raises(ValueError):
        Runtime(journal, engine, capacity=0)
    with pytest.raises(ValueError):
        asyncio.run(Runtime(journal, engine).run(checkpoint_interval=0))
    journal.close()


def test_ndjson_and_real_disk_budget(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    record = Record("s", 0, 0)
    path.write_text(record.wire() + "\n")
    assert list(read_ndjson(path)) == [record]
    path.write_text("x" * 17000)
    with pytest.raises(ValueError):
        list(read_ndjson(path))
    path.write_text("[]\n")
    with pytest.raises(ValueError):
        list(read_ndjson(path))
    import sqlite3

    journal = Journal(tmp_path / "limited.db", max_disk_bytes=40960)
    with pytest.raises(sqlite3.OperationalError, match="full"):
        journal.admit([replace(record, source_offset=i, payload="x" * 8000) for i in range(50)])
    assert not journal.read(0)
    journal.close()


def test_worker_exception_propagates_and_cancels(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "j.db")
    journal.admit([Record("s", 0, 0)])

    def broken(value: int) -> int:
        raise ValueError("mapper failed")

    with pytest.raises(ExceptionGroup, match="TaskGroup"):
        asyncio.run(Runtime(journal, journal.recover(Config((INPUT,))), mapper=broken).run())
    assert journal.recover(Config((INPUT,))).position == 0
    journal.close()


def test_delivery_canonical_identity() -> None:
    from pp_current import Delivery

    with pytest.raises(ValueError, match="identity"):
        Delivery("j", "o", "key", 0, "{}")
    with pytest.raises(ValueError, match="canonical"):
        Delivery("j", "o", "key", 1, '{ "x":1 }')


@pytest.mark.parametrize(
    "field", ["workers", "size", "slide", "lateness", "join_interval", "state_limit"]
)
@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_configuration_rejects_noninteger_limits(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        Config((INPUT,), **{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("identity", [(1, "op", "key"), ("job", 1, "key"), ("job", "op", None)])
def test_delivery_rejects_nonstring_identity(identity: tuple[object, object, object]) -> None:
    from pp_current import Delivery

    with pytest.raises(ValueError, match="identity"):
        Delivery(*identity, 1, "{}")  # type: ignore[arg-type]
