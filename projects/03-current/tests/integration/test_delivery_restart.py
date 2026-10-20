"""Independent job namespaces, sink rollback and process death before acknowledgement."""

import asyncio
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from pp_current import Config, Delivery, IdempotentSink, Journal, Record, Runtime, canonical


@pytest.mark.parametrize("point", ["seen_insert", "latest_insert"])
def test_sink_failure_never_commits_half_a_delivery(tmp_path: Path, point: str) -> None:
    sink = IdempotentSink(tmp_path / "sink.db")
    table = "seen" if point == "seen_insert" else "latest"
    delivery = Delivery("a", "window", "key", 1, '{"sum":3}')
    try:
        sink.db.execute(
            f"CREATE TEMP TRIGGER fail_write AFTER INSERT ON {table} BEGIN SELECT RAISE(ABORT,'injected sink failure'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="sink failure"):
            sink.put(delivery)
        assert sink.db.execute("SELECT count(*) FROM seen").fetchone() == (0,)
        assert sink.db.execute("SELECT count(*) FROM latest").fetchone() == (0,)
        sink.db.execute("DROP TRIGGER fail_write")
        sink.put(delivery)
        assert sink.db.execute("SELECT count(*) FROM seen").fetchone() == (1,)
        assert sink.db.execute("SELECT payload FROM latest").fetchone() == (delivery.payload,)
    finally:
        sink.close()


def test_two_jobs_reordered_revisions_and_crash_after_sink_commit(tmp_path: Path) -> None:
    config = Config((canonical(["s", 0]),), size=10, slide=10, lateness=2, join_interval=0)
    paths = [tmp_path / "a.db", tmp_path / "b.db"]
    expected: dict[tuple[str, str, str], tuple[int, str]] = {}
    for name, path, value in zip(("job-a", "job-b"), paths, (3, 30), strict=True):
        journal = Journal(path)
        try:
            journal.admit(
                [
                    Record("s", 0, 0, 1, "same", value),
                    Record("s", 0, 1, 10, kind="watermark"),
                    Record("s", 0, 2, 9, "same", value + 1),
                    Record("s", 0, 3, kind="end"),
                ]
            )
            asyncio.run(
                Runtime(journal, journal.recover(config, job_id=name)).run(checkpoint_interval=2)
            )
            for delivery in journal.pending():
                identity = delivery.job_id, delivery.operator_id, delivery.logical_result_key
                if identity not in expected or expected[identity][0] < delivery.revision:
                    expected[identity] = delivery.revision, delivery.payload
        finally:
            journal.close()
    sink_path = tmp_path / "sink.db"
    script = """
import os, sys
from pathlib import Path
from pp_current import Journal, IdempotentSink
journal = Journal(Path(sys.argv[1]))
sink = IdempotentSink(Path(sys.argv[2]))
sink.put(journal.pending(100)[-1])
os._exit(73)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(paths[0]), str(sink_path)],
        capture_output=True,
        timeout=15,
    )
    assert completed.returncode == 73, completed.stderr.decode()
    sink = IdempotentSink(sink_path)
    try:
        for path in reversed(paths):
            journal = Journal(path)
            try:
                deliveries = journal.pending()
                assert len(deliveries) == 4  # the killed process acknowledged nothing
                for delivery in sorted(deliveries, key=lambda row: -row.revision):
                    sink.put(delivery)
                    journal.acknowledge(delivery)
                assert journal.pending() == []
                assert journal.recover(config).position == 4
            finally:
                journal.close()
        actual = {
            (job, operator, key): (revision, payload)
            for job, operator, key, revision, payload in sink.db.execute("SELECT * FROM latest")
        }
        assert actual == expected
        assert sink.db.execute("SELECT count(*) FROM seen").fetchone() == (8,)
    finally:
        sink.close()
