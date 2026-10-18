import asyncio
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pp_current import (
    BudgetExceeded,
    Config,
    Delivery,
    Engine,
    IdempotentSink,
    Journal,
    Record,
    Runtime,
    canonical,
)

INPUT = canonical(["s", 0])


def test_admission_lost_ack_conflicts_and_offset_identity(tmp_path: Path) -> None:
    def failure(point: str) -> None:
        if point == "admission-after-commit":
            raise OSError("lost acknowledgement")

    journal = Journal(tmp_path / "j.db", failpoint=failure)
    record = Record("s", 0, 0, event_id="repeat")
    with pytest.raises(OSError):
        journal.admit([record])
    journal.close()
    journal = Journal(tmp_path / "j.db")
    assert journal.admit([record])[0].ingress_ordinal == 1
    assert journal.replayed == 1
    with pytest.raises(ValueError, match="conflicting"):
        journal.admit([replace(record, value=1)])
    assert journal.admit([replace(record, source_offset=1)])[0].ingress_ordinal == 2
    journal.close()


@pytest.mark.parametrize(
    "point",
    [
        "checkpoint-before-stage",
        "checkpoint-during-stage",
        "checkpoint-before-publication",
        "checkpoint-after-publication",
    ],
)
def test_process_kill_checkpoint_prefix(tmp_path: Path, point: str) -> None:
    path = tmp_path / "journal.db"
    journal = Journal(path)
    records = [Record("s", 0, 0, value=3), Record("s", 0, 1, 30_000, kind="watermark")]
    admitted = journal.admit(records)
    engine = Engine(Config((INPUT,)))
    engine.apply(admitted[0])
    journal.publish(engine)
    journal.close()
    code = """
import os, sys
from pathlib import Path
from pp_current import *
j = Journal(Path(sys.argv[1]), failpoint=lambda p: os._exit(73) if p == sys.argv[2] else None)
e = j.recover(Config((canonical(['s',0]),)))
for r in j.read(e.position): e.apply(r)
j.publish(e)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path), point], capture_output=True, timeout=20
    )
    assert result.returncode == 73, result.stderr.decode()
    journal = Journal(path)
    engine = journal.recover(Config((INPUT,)))
    assert engine.position == (2 if point.endswith("after-publication") else 1)
    for record in journal.read(engine.position):
        engine.apply(record)
    journal.publish(engine)
    outputs = journal.export()
    assert any(row["payload"]["sum"] == 3 for row in outputs)  # type: ignore[index]
    assert journal.recover(Config((INPUT,))).position == 2
    journal.close()


def test_sink_lost_ack_out_of_order_and_conflicting_revision(tmp_path: Path) -> None:
    sink = IdempotentSink(tmp_path / "sink.db")
    first = Delivery("job", "window", '["",0,10]', 1, '{"count":1}')
    second = replace(first, revision=2, payload='{"count":2}')
    sink.put(first)
    sink.put(second)
    sink.close()  # acknowledgement may be lost after sink commit
    sink = IdempotentSink(tmp_path / "sink.db")
    sink.put(first)
    assert sink.db.execute("SELECT revision,payload FROM latest").fetchone() == (2, second.payload)
    with pytest.raises(ValueError, match="conflicting"):
        sink.put(replace(first, payload='{"count":9}'))
    sink.close()


def test_bounded_async_hot_key_and_writer_stall(tmp_path: Path) -> None:
    import time

    journal = Journal(tmp_path / "j.db")
    records = [Record("s", 0, i, i, "hot" if i % 2 else str(i), i) for i in range(100)]
    records.append(Record("s", 0, 100, kind="end"))
    journal.admit(records)
    runtime = Runtime(journal, journal.recover(Config((INPUT,))), capacity=3)
    ticks = 0

    def stall(point: str) -> None:
        if point == "checkpoint-during-stage":
            time.sleep(0.015)

    journal.failpoint = stall

    async def scenario() -> None:
        nonlocal ticks
        task = asyncio.create_task(runtime.run(checkpoint_interval=10))
        while not task.done():
            ticks += 1
            await asyncio.sleep(0.001)
        await task

    asyncio.run(scenario())
    assert ticks >= 20 and runtime.metrics.queue_peak <= 3
    assert runtime.engine.dispositions["on-time"] == 100
    journal.close()
    constrained = Journal(tmp_path / "limited.db", max_records=1, max_outbox=0)
    with pytest.raises(BudgetExceeded):
        constrained.admit(records[:2])
    assert constrained.read(0) == []
    engine = Engine(Config((INPUT,)))
    for record in constrained.admit([records[0]]):
        engine.apply(record)
    engine.pending.append(Delivery("j", "op", "key", 1, "{}"))
    with pytest.raises(BudgetExceeded):
        constrained.publish(engine)
    assert constrained.recover(engine.config).position == 0
    constrained.close()


def test_map_filter_and_replay_no_double_application(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "j.db")
    records = [Record("s", 0, i, i, value=i) for i in range(5)]
    records.append(Record("s", 0, 5, kind="end"))
    journal.admit(records)
    config = Config((INPUT,))
    runtime = Runtime(
        journal, journal.recover(config), mapper=lambda n: n * 2, predicate=lambda r: r.value != 4
    )
    asyncio.run(runtime.run())
    before = journal.export()
    journal.admit(records)
    asyncio.run(Runtime(journal, journal.recover(config)).run())
    assert journal.export() == before
    assert next(r["payload"] for r in before if r["operator_id"] == "tumbling")["sum"] == 16  # type: ignore[index]
    journal.close()


@pytest.mark.parametrize("invalid", ["unknown", "idle", "ended"])
def test_filtered_events_preserve_input_lifecycle_checks(tmp_path: Path, invalid: str) -> None:
    journal = Journal(tmp_path / "filtered.db")
    records = []
    if invalid != "unknown":
        records.append(Record("s", 0, 0, kind="idle" if invalid == "idle" else "end"))
    records.append(Record("other" if invalid == "unknown" else "s", 0, 1))
    journal.admit(records)
    config = Config((INPUT,))
    runtime = Runtime(journal, journal.recover(config), predicate=lambda _: False)
    with pytest.raises(ExceptionGroup):
        asyncio.run(runtime.run())
    assert journal.recover(config).position == 0
    journal.close()


def test_recovery_rejects_different_job_identity(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "jobs.db")
    config = Config((INPUT,))
    journal.publish(journal.recover(config, job_id="original"))
    with pytest.raises(ValueError, match="job"):
        journal.recover(config, job_id="different")
    assert journal.recover(config).job_id == "original"
    journal.close()


def test_acknowledgement_must_match_registered_payload(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "ack.db")
    engine = journal.recover(Config((INPUT,)))
    delivery = Delivery("demo", "window", "key", 1, '{"count":1}')
    engine.pending.append(delivery)
    journal.publish(engine)
    with pytest.raises(ValueError, match="delivery"):
        journal.acknowledge(replace(delivery, payload='{"count":2}'))
    with pytest.raises(ValueError, match="delivery"):
        journal.acknowledge(replace(delivery, revision=2))
    assert journal.pending() == [delivery]
    journal.acknowledge(delivery)
    journal.acknowledge(delivery)
    assert journal.pending() == []
    journal.close()


def test_failed_admission_does_not_increment_committed_replay_count(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "replays.db")
    record = Record("s", 0, 0)
    journal.admit([record])
    with pytest.raises(ValueError, match="conflicting"):
        journal.admit([record, replace(record, value=1)])
    assert journal.replayed == 0
    journal.admit([record])
    assert journal.replayed == 1
    journal.close()


def test_mapper_cannot_smuggle_equal_float_through_integer_validation(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "mapper.db")
    journal.admit([Record("s", 0, 0, value=1)])
    runtime = Runtime(journal, journal.recover(Config((INPUT,))), mapper=lambda _: 1.0)  # type: ignore[arg-type,return-value]
    with pytest.raises(ExceptionGroup):
        asyncio.run(runtime.run())
    assert journal.recover(Config((INPUT,))).position == 0
    journal.close()


def test_read_only_journal_enforces_sqlite_write_protection(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "read-only.db"
    journal = Journal(path)
    journal.admit([Record("s", 0, 0)])
    journal.close()
    journal = Journal(path, read_only=True)
    assert len(journal.read(0)) == 1
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        journal.admit([Record("s", 0, 1)])
    journal.close()


def test_previous_code_checkpoint_rejection_preserves_database(tmp_path: Path) -> None:
    from pp_current.runtime.engine import CODE_VERSION

    path = tmp_path / "previous-version.db"
    config = Config((INPUT,))
    journal = Journal(path)
    record = journal.admit([Record("s", 0, 0, value=7)])[0]
    engine = journal.recover(config)
    engine.apply(record)
    journal.publish(engine)
    previous = engine.dump().replace(CODE_VERSION, "current-1")
    journal.db.execute("UPDATE checkpoint SET state=?", (previous,))
    journal.close()
    before = path.read_bytes()
    journal = Journal(path, read_only=True)
    with pytest.raises(ValueError, match="incompatible"):
        journal.recover(config)
    assert journal.db.execute("SELECT state FROM checkpoint").fetchone() == (previous,)
    assert journal.read(0) == [record]
    journal.close()
    assert path.read_bytes() == before
