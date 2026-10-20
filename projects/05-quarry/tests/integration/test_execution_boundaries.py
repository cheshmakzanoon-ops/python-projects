"""Numeric, parser, history and reader-lifetime boundaries under interleaving."""

from __future__ import annotations

import csv
import gc
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event as Signal
from typing import Any

import duckdb
import pytest

from pp_quarry import Config, Contract, Field, Lakehouse, Snapshot, recover
from pp_quarry.execution import engine as execution
from pp_quarry.model.events import Event
from pp_quarry.planning.partitions import bucket
from pp_quarry.sources import read
from tests.conftest import event, source


@pytest.mark.parametrize("buckets", [1, 2])
def test_overflowing_daily_reduction_cannot_publish_partial_state(
    tmp_path: Path, buckets: int
) -> None:
    first_key = "first"
    first_bucket = bucket(Event("devices", first_key, 1, "upsert", {}).key_bytes, buckets)
    second_key = next(
        str(number)
        for number in range(100)
        if buckets == 1
        or bucket(Event("devices", str(number), 1, "upsert", {}).key_bytes, buckets) != first_bucket
    )
    with Lakehouse(tmp_path / "lake", Config(buckets=buckets)) as lake:
        first = lake.ingest(
            source(
                tmp_path,
                [event(first_key, value=1e308), event(second_key, value=1e308, day="2026-01-02")],
            )
        )
        with Snapshot(lake.root, first) as pinned:
            before = list(pinned.rows("daily"))
            invalid = source(
                tmp_path,
                [event(first_key, version=0), event(second_key, version=2, value=1e308)],
                name="overflow.ndjson",
            )
            with pytest.raises(ValueError, match="finite DOUBLE"):
                lake.ingest(invalid)
            assert lake.snapshots() == [first]
            assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 2
            assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
            assert list(pinned.rows("daily")) == before
            assert recover(lake)["removed_orphans"]
            lake.ingest(
                source(
                    tmp_path, [event(second_key, version=2, value=-1e308)], name="corrected.ndjson"
                )
            )
            with Snapshot(lake.root) as current:
                assert list(current.rows("daily")) == [
                    {"day": "2026-01-01", "count": 2, "total": 0.0}
                ]
            assert list(pinned.rows("daily")) == before


def test_interleaved_csv_readers_restore_and_isolate_the_global_field_limit(
    tmp_path: Path,
) -> None:
    large = tmp_path / "large.csv"
    small = tmp_path / "small.csv"
    for path, rows in (
        (large, [("first", "{}"), ("large", json.dumps({"extra": "x" * 300}))]),
        (small, [("small", "{}")]),
    ):
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["key", "version", "operation", "payload"])
            for key, payload in rows:
                writer.writerow([key, 1, "upsert", payload])
    before = csv.field_size_limit()
    records = read(large, 4096)
    try:
        assert next(records)[1].key == "first"
        assert next(read(small, 128))[1].key == "small"
        assert next(records)[1].payload == {"extra": "x" * 300}
        assert csv.field_size_limit() == before
    finally:
        records.close()
        csv.field_size_limit(before)


def test_closing_snapshot_closes_a_partially_consumed_query_before_unpinning(
    lake: Lakehouse, tmp_path: Path
) -> None:
    first = lake.ingest(source(tmp_path, [event(str(number)) for number in range(5)]))
    pinned = Snapshot(lake.root, first)
    rows = pinned.rows()
    next(rows)
    lake.ingest(
        source(tmp_path, [event(str(number), version=2) for number in range(5)], name="new.ndjson")
    )
    pinned.close()
    recover(lake, retain=1)
    with pytest.raises(StopIteration):
        next(rows)
    assert lake.db.execute("SELECT count(*) FROM pins").fetchone()[0] == 0
    assert lake.snapshots() == [first + 1]
    lake.validate()


def test_history_pages_are_bounded_and_freeze_late_arrivals_across_retention(
    lake: Lakehouse, tmp_path: Path
) -> None:
    first = lake.ingest(source(tmp_path, [event(version=version) for version in range(1500)]))
    page = lake.lineage("devices", "x")
    assert len(page["versions"]) == 1000
    assert [row["version"] for row in page["versions"]] == list(range(1000))
    assert page["as_of_snapshot"] == first
    assert page["next_after_version"] == 999
    lake.ingest(source(tmp_path, [event(version=1500)], name="new.ndjson"))
    recover(lake, retain=1)
    rest = lake.lineage(
        "devices", "x", after_version=page["next_after_version"], as_of_snapshot=first
    )
    assert [row["version"] for row in rest["versions"]] == list(range(1000, 1500))
    assert rest["next_after_version"] is None


def test_history_cutoff_excludes_new_obsolete_versions_below_the_cursor(
    lake: Lakehouse, tmp_path: Path
) -> None:
    first = lake.ingest(source(tmp_path, [event(version=version) for version in (0, 10, 20, 30)]))
    page = lake.lineage("devices", "x", limit=2)
    assert [row["version"] for row in page["versions"]] == [0, 10]
    lake.ingest(source(tmp_path, [event(version=5), event(version=40)], name="late.ndjson"))
    recover(lake, retain=1)
    rest = lake.lineage("devices", "x", after_version=10, as_of_snapshot=first)
    assert [row["version"] for row in rest["versions"]] == [20, 30]
    fresh = lake.lineage("devices", "x")
    assert [row["version"] for row in fresh["versions"]] == [0, 5, 10, 20, 30, 40]


def test_validation_pins_its_selected_snapshot_during_concurrent_retention(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    keys = {
        bucket(Event("devices", str(number), 1, "upsert", {}).key_bytes, 2): str(number)
        for number in range(20)
    }
    assert set(keys) == {0, 1}
    first = lake.ingest(source(tmp_path, [event(key) for key in keys.values()]))
    reading, resume = Signal(), Signal()
    verify = execution.verify_entry

    def pause(root: Path, entry: dict[str, object]) -> Path:
        reading.set()
        assert resume.wait(10), "validator was not resumed"
        return verify(root, entry)

    monkeypatch.setattr(execution, "verify_entry", pause)

    def validate() -> dict[str, int]:
        with Lakehouse(lake.root) as reader:
            return reader.validate(first)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(validate)
        try:
            assert reading.wait(10), "validator did not reach file reads"
            lake.ingest(
                source(
                    tmp_path, [event(key, version=2) for key in keys.values()], name="new.ndjson"
                )
            )
            recover(lake, retain=1)
        finally:
            resume.set()
        assert future.result(timeout=10) == {"files": 6, "rows": 6}
    recover(lake, retain=1)
    assert lake.snapshots() == [first + 1]


def test_quality_policy_changes_revalidate_without_rewriting_unchanged_data(
    lake: Lakehouse, tmp_path: Path
) -> None:
    incoming = source(tmp_path, [event(value=3)])
    first = lake.ingest(incoming)
    before = lake.manifest(first)
    tighter = Contract(minimum=0, maximum=10, min_rows=1, max_rows=5)
    plan = lake.plan(incoming, tighter)
    assert all(
        node["action"] == "reuse"
        for nodes in plan["partitions"].values()
        for node in nodes.values()
    )
    second = lake.ingest(incoming, tighter)
    assert lake.manifest(second)["stats"]["bytes_written"] == 0
    assert lake.manifest(second)["stats"]["reused_nodes"] == 6
    for partition, nodes in before["partitions"].items():
        for name, entry in nodes.items():
            assert lake.manifest(second)["partitions"][partition][name]["path"] == entry["path"]
    files = set((lake.root / "data").iterdir())
    with pytest.raises(ValueError, match="minimum"):
        lake.ingest(incoming, Contract(minimum=4))
    assert lake.snapshots() == [first, second]
    assert set((lake.root / "data").iterdir()) == files


def test_nullable_schema_addition_reuses_fixed_normalization_and_preserves_old_schema(
    lake: Lakehouse, tmp_path: Path
) -> None:
    first = lake.ingest(source(tmp_path, [event(str(number)) for number in range(8)]))
    before = lake.manifest(first)
    evolved = Contract({**Contract().fields, "firmware": Field("string", True)})
    empty = source(tmp_path, [], name="schema-only.ndjson")
    with Snapshot(lake.root, first) as old:
        daily = list(old.rows("daily"))
        plan = lake.plan(empty, evolved)
        assert all(
            nodes["normalized"]["action"] == "reuse" for nodes in plan["partitions"].values()
        )
        lake.ingest(empty, evolved)
        after = lake.manifest()
        for partition in before["partitions"]:
            assert (
                after["partitions"][partition]["normalized"]["path"]
                == before["partitions"][partition]["normalized"]["path"]
            )
            assert (
                after["partitions"][partition]["facts"]["path"]
                != before["partitions"][partition]["facts"]["path"]
            )
        with Snapshot(lake.root) as current:
            assert all(row["payload__firmware"] is None for row in current.rows())
            assert list(current.rows("daily")) == daily
        assert all("payload__firmware" not in row for row in old.rows())


def test_caller_field_mapping_cannot_change_contract_between_staging_and_publication(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake.ingest(source(tmp_path, [event()]))
    fields = dict(Contract().fields)
    chosen = Contract(fields)
    original = execution.read

    def change_after_validation(*args: object, **kwargs: object):
        yield from original(*args, **kwargs)
        fields["value"] = Field("integer")

    monkeypatch.setattr(execution, "read", change_after_validation)
    lake.ingest(source(tmp_path, [event(version=2, value=3.5)], name="new.ndjson"), chosen)
    assert fields["value"].kind == "integer"
    assert chosen.fields["value"].kind == "number"
    assert lake.manifest()["contract"]["fields"]["value"]["kind"] == "number"
    with Snapshot(lake.root) as pinned:
        assert next(pinned.rows())["value"] == 3.5


def test_legacy_nonfinite_daily_results_fail_before_a_limited_query_yields(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Recreate the previously published outcome without modifying catalog or
    # Parquet metadata, then exercise reader/validator guards independently.
    with monkeypatch.context() as patch:
        patch.setattr(execution, "check_daily_totals", lambda *_: None)
        snapshot = lake.ingest(
            source(
                tmp_path,
                [
                    event("valid", value=1),
                    event("large-a", value=1e308, day="2026-01-02"),
                    event("large-b", value=1e308, day="2026-01-02"),
                ],
            )
        )
    with Snapshot(lake.root, snapshot) as pinned:
        assert len(list(pinned.rows())) == 3
        with pytest.raises(ValueError, match="finite DOUBLE"):
            next(pinned.rows("daily", limit=1))
    with pytest.raises(ValueError, match="finite DOUBLE"):
        lake.validate(snapshot)


def test_abandoned_query_closes_its_engine_without_releasing_the_snapshot_pin(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake.ingest(source(tmp_path, [event(str(number)) for number in range(5)]))
    original = duckdb.connect
    connections = []

    def track() -> duckdb.DuckDBPyConnection:
        connection = original()
        connections.append(connection)
        return connection

    monkeypatch.setattr(duckdb, "connect", track)
    with Snapshot(lake.root) as pinned:
        reader = pinned.rows()
        next(reader)
        del reader
        gc.collect()
        with pytest.raises(duckdb.ConnectionException, match="closed"):
            connections[0].execute("SELECT 1")
        assert lake.db.execute("SELECT count(*) FROM pins").fetchone()[0] == 1
    assert lake.db.execute("SELECT count(*) FROM pins").fetchone()[0] == 0


def test_gc_recomputes_references_when_publication_enters_between_its_transactions(
    lake: Lakehouse, tmp_path: Path
) -> None:
    lake.ingest(source(tmp_path, [event(str(number)) for number in range(8)]))
    second = lake.ingest(
        source(
            tmp_path, [event(str(number), version=2) for number in range(8)], name="second.ndjson"
        )
    )
    retained, resume = Signal(), Signal()

    class PauseCommit:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection
            self.commits = 0

        def __getattr__(self, name: str) -> Any:
            return getattr(self.connection, name)

        def commit(self) -> None:
            self.connection.commit()
            self.commits += 1
            if self.commits == 1:
                retained.set()
                assert resume.wait(10), "reclamation was not resumed"

    def reclaim() -> dict[str, Any]:
        with Lakehouse(lake.root) as collector:
            collector.db = PauseCommit(collector.db)  # type: ignore[assignment]
            return recover(collector, retain=1)

    with Snapshot(lake.root, second) as old:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reclaim)
            try:
                assert retained.wait(10), "retention did not commit"
                third = lake.ingest(
                    source(
                        tmp_path,
                        [event(str(number), version=3, value=9) for number in range(8)],
                        name="third.ndjson",
                    )
                )
            finally:
                resume.set()
            report = future.result(timeout=10)
        assert report["snapshots"] == [second, third]
        assert {row["version"] for row in old.rows()} == {2}
        with Snapshot(lake.root, third) as current:
            assert {row["value"] for row in current.rows()} == {9.0}
        lake.validate(third)
    recover(lake, retain=1)
    assert lake.snapshots() == [third]


def test_lineage_cli_exposes_the_same_stable_page_cursor(
    lake: Lakehouse,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pp_quarry.cli import main

    snapshot = lake.ingest(source(tmp_path, [event(version=version) for version in (0, 10, 20)]))
    monkeypatch.setattr(
        "sys.argv",
        [
            "quarry",
            "lineage",
            "--dataset",
            str(lake.root),
            "--namespace",
            "devices",
            "--key",
            "x",
            "--limit",
            "1",
            "--after-version",
            "0",
            "--as-of-snapshot",
            str(snapshot),
        ],
    )
    main()
    page = json.loads(capsys.readouterr().out)
    assert [row["version"] for row in page["versions"]] == [10]
    assert page["next_after_version"] == 10
    assert page["as_of_snapshot"] == snapshot
