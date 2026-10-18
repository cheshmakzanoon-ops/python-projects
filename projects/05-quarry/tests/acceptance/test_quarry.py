from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pp_quarry import Config, Conflict, Contract, Field, InjectedCrash, Lakehouse, Snapshot, recover
from pp_quarry.planning.dag import Node
from tests.conftest import event, source


def facts(lake: Lakehouse, snapshot: int | None = None) -> dict[str, tuple[int, dict[str, Any]]]:
    with Snapshot(lake.root, snapshot) as handle:
        return {row["key"]: (row["version"], json.loads(row["payload"])) for row in handle.rows()}


def test_qu01_out_of_order_repeat_independent_rebuild(lake: Lakehouse, tmp_path: Path) -> None:
    batches = [
        [event("a", 1, 2), event("b", 2, 8)],
        [event("a", 3, 9), event("b", 1, 5)],
        [event("a", 2, 4), event("c", 0, 1)],
    ]
    expected: dict[str, dict[str, Any]] = {}
    for index, rows in enumerate(batches):
        path = source(tmp_path, rows, f"{index}.ndjson")
        lake.ingest(path)
        lake.ingest(path)
        for row in rows:
            old = expected.get(row["key"])
            if old is None or row["version"] > old["version"]:
                expected[row["key"]] = row
        assert facts(lake) == {
            key: (row["version"], row["payload"]) for key, row in expected.items()
        }
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 3
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 6
    assert lake.manifest()["stats"]["reused_nodes"] == 6


def test_qu02_historical_conflict_survives_tombstone_gc_restart(tmp_path: Path) -> None:
    root = tmp_path / "lake"
    first = source(tmp_path, [event()], "first.ndjson")
    with Lakehouse(root, Config(buckets=2)) as lake:
        lake.ingest(first)
        lake.ingest(source(tmp_path, [event(version=3, operation="delete")], "delete.ndjson"))
        lake.ingest(source(tmp_path, [event(version=2, value=7)], "older.ndjson"))
        lake.build(force=True)
        recover(lake, retain=1)
        assert facts(lake) == {}
    with Lakehouse(root) as lake:
        with pytest.raises(Conflict, match="historical"):
            lake.ingest(source(tmp_path, [event(version=1, value=100)], "conflict.ndjson"))
        assert lake.lineage("devices", "x")["versions"][0]["version"] == 1
        assert len(lake.snapshots()) == 1
        assert facts(lake) == {}


def test_qu03_one_bucket_plan_reuse_and_moving_day(lake: Lakehouse, tmp_path: Path) -> None:
    lake.ingest(source(tmp_path, [event("a"), event("b")]))
    old = lake.manifest()
    correction = source(tmp_path, [event("a", 2, 8, day="2026-01-02")], "correction.ndjson")
    plan = lake.plan(correction)
    changed = [
        part for part, nodes in plan["partitions"].items() if nodes["facts"]["action"] == "build"
    ]
    assert len(changed) == 1
    lake.ingest(correction)
    assert lake.manifest()["stats"]["rewritten_buckets"] == 1
    for part, nodes in lake.manifest()["partitions"].items():
        if part not in changed:
            assert nodes["facts"]["path"] == old["partitions"][part]["facts"]["path"]
    with Snapshot(lake.root) as handle:
        assert list(handle.rows("daily")) == [
            {"day": "2026-01-01", "count": 1, "total": 3.0},
            {"day": "2026-01-02", "count": 1, "total": 8.0},
        ]
    lake.ingest(source(tmp_path, [event("a", 3, operation="delete")], "remove.ndjson"))
    with Snapshot(lake.root) as handle:
        assert list(handle.rows("daily")) == [{"day": "2026-01-01", "count": 1, "total": 3.0}]


def test_qu04_strict_rollback_and_invalid_dag(lake: Lakehouse, tmp_path: Path) -> None:
    path = source(tmp_path, [event("valid"), event("bad", value=-9)])
    with pytest.raises(ValueError, match="minimum"):
        lake.ingest(path, Contract(minimum=0))
    assert lake.snapshots() == []
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 0
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 0
    with pytest.raises(ValueError, match="cycle"):
        lake.ingest(path, dag=(Node("a", "facts", ("a",)),))
    source(tmp_path, [event("valid")]).write_text('{"key":')
    with pytest.raises(json.JSONDecodeError):
        lake.ingest(path)
    assert not lake.snapshots()


def test_qu05_evolution_preserves_old_snapshots(lake: Lakehouse, tmp_path: Path) -> None:
    first = lake.ingest(source(tmp_path, [event()]))
    contract = Contract({**Contract().fields, "firmware": Field("string", True)})
    lake.ingest(source(tmp_path, [event("y", firmware="2.1")], "evolution.ndjson"), contract)
    assert "firmware" not in facts(lake, first)["x"][1]
    assert facts(lake)["y"][1]["firmware"] == "2.1"
    with pytest.raises(ValueError, match="migration"):
        lake.ingest(source(tmp_path, [event("z")], "bad-schema.ndjson"), Contract())
    assert len(lake.snapshots()) == 2


@pytest.mark.parametrize(
    "boundary,committed", [("after_files", False), ("before_commit", False), ("after_commit", True)]
)
def test_qu06_fault_transaction_boundary(
    lake: Lakehouse, tmp_path: Path, boundary: str, committed: bool
) -> None:
    path = source(tmp_path, [event()])
    with pytest.raises(InjectedCrash):
        lake.ingest(path, fault=boundary)
    assert bool(lake.snapshots()) is committed
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == int(committed)
    report = recover(lake)
    assert bool(report["removed_orphans"]) is not committed
    lake.ingest(path)
    assert facts(lake)["x"][0] == 1
    lake.validate()


def test_qu07_pin_during_publication_gc_retains_reader(lake: Lakehouse, tmp_path: Path) -> None:
    old = lake.ingest(source(tmp_path, [event()]))
    with Snapshot(lake.root, old) as pinned:
        lake.ingest(source(tmp_path, [event(version=2, value=20)], "new.ndjson"))
        recover(lake, retain=1)
        assert old in lake.snapshots()
        assert next(pinned.rows())["value"] == 3
        assert next(iter(facts(lake).values()))[0] == 2
    recover(lake, retain=1)
    assert old not in lake.snapshots()
    with pytest.raises(ValueError, match="unknown snapshot"):
        lake.manifest(old)


def test_qu08_bounded_batch_and_wrong_record_lineage(lake: Lakehouse, tmp_path: Path) -> None:
    path = source(tmp_path, [event(str(i), value=i) for i in range(100)])
    lake.ingest(path)
    assert lake.manifest()["stats"]["max_batch_rows"] <= 8
    trace = lake.lineage("devices", "77")
    offset = trace["versions"][0]["offset"]
    assert json.loads(path.read_bytes()[:offset].splitlines()[-1])["payload"]["value"] == 77
    assert trace["columns"]["daily.total"] == "sum(facts.value)"
    assert lake.validate()["files"] == 6


def test_global_quality_rule_rejects_repeated_source(lake: Lakehouse, tmp_path: Path) -> None:
    path = source(tmp_path, [event(value=-10)])
    lake.ingest(path)
    with pytest.raises(ValueError, match="dataset minimum"):
        lake.ingest(path, Contract(minimum=0))
    assert len(lake.snapshots()) == 1
    with pytest.raises(ValueError, match="row-count"):
        lake.ingest(source(tmp_path, [event("y")], "row-limit.ndjson"), Contract(max_rows=1))
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 1


@pytest.mark.parametrize("dag", [(), (Node("normalized", "normalize"),)])
def test_incomplete_declarative_pipeline_never_publishes(
    lake: Lakehouse, tmp_path: Path, dag: tuple[Node, ...]
) -> None:
    with pytest.raises(ValueError, match="unsupported pipeline configuration"):
        lake.ingest(source(tmp_path, [event()]), dag=dag)
    assert not lake.snapshots()
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 0
