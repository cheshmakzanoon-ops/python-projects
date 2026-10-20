"""Published snapshots must never silently consume modified Parquet content."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pp_quarry import Lakehouse, Snapshot, recover
from pp_quarry.execution import engine
from tests.conftest import event, source


def test_queries_and_reuse_reject_rewritten_valid_parquet(lake: Lakehouse, tmp_path: Path) -> None:
    snapshot = lake.ingest(source(tmp_path, [event(value=3)]))
    with Snapshot(lake.root, snapshot) as pinned:
        assert next(pinned.rows())["value"] == 3
    entry = next(
        nodes["facts"]
        for nodes in lake.manifest(snapshot)["partitions"].values()
        if nodes["facts"]["rows"]
    )
    path = lake.root / entry["path"]
    table = pq.read_table(path)
    table = table.set_column(table.schema.get_field_index("value"), "value", pa.array([999.0]))
    pq.write_table(table, path, compression="zstd")
    # The replacement is valid Parquet with the same row count and schema.
    assert pq.read_table(path).column("value").to_pylist() == [999.0]
    assert str(pq.read_schema(path)) == entry["schema"]
    with pytest.raises(ValueError, match="checksum/size"):
        with Snapshot(lake.root, snapshot) as pinned:
            list(pinned.rows())
    with pytest.raises(ValueError, match="checksum/size"):
        lake.validate(snapshot)
    # An obsolete version adds an identity without changing current state.
    # Reuse failure must roll back both that identity and its checkpoint.
    with pytest.raises(ValueError, match="checksum/size"):
        lake.ingest(source(tmp_path, [event(version=0)], name="obsolete.ndjson"))
    assert lake.snapshots() == [snapshot]
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 1
    assert lake.db.execute("SELECT count(*) FROM pins").fetchone()[0] == 0


@pytest.mark.parametrize("field", ["rows", "schema"])
def test_queries_reject_manifest_metadata_mismatch(
    lake: Lakehouse, tmp_path: Path, field: str
) -> None:
    snapshot = lake.ingest(source(tmp_path, [event()]))
    manifest = lake.manifest(snapshot)
    entry = manifest["partitions"]["0"]["facts"]
    # Keep the real content checksum; metadata must be independently checked.
    path = lake.root / entry["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    entry[field] = entry[field] + 1 if field == "rows" else "unexpected schema"
    lake.db.execute("UPDATE snapshots SET manifest=? WHERE id=?", (json.dumps(manifest), snapshot))
    lake.db.commit()
    with pytest.raises(ValueError, match="row count|schema"):
        with Snapshot(lake.root, snapshot) as pinned:
            list(pinned.rows())


@pytest.mark.parametrize("limit", [True, 1.5, "1; SELECT 1"])
def test_query_limit_requires_a_nonnegative_integer(
    lake: Lakehouse, tmp_path: Path, limit: int
) -> None:
    lake.ingest(source(tmp_path, [event()]))
    with Snapshot(lake.root) as pinned:
        with pytest.raises(ValueError, match="limit"):
            list(pinned.rows(limit=limit))


def test_recovery_rejects_unsafe_references_before_pruning_or_deleting(
    lake: Lakehouse, tmp_path: Path
) -> None:
    first = lake.ingest(source(tmp_path, [event()]))
    latest = lake.ingest(source(tmp_path, [event(version=2)], name="updated.ndjson"))
    manifest = lake.manifest(latest)
    manifest["partitions"]["0"]["facts"]["path"] = "data/*.parquet"
    lake.db.execute("UPDATE snapshots SET manifest=? WHERE id=?", (json.dumps(manifest), latest))
    lake.db.commit()
    orphan = lake.root / "data" / "unpublished.parquet"
    orphan.write_bytes(b"orphan")
    before = set((lake.root / "data").iterdir())
    with pytest.raises(ValueError, match="manifest path"):
        recover(lake, retain=1)
    assert lake.snapshots() == [first, latest]
    assert set((lake.root / "data").iterdir()) == before


def test_malformed_stored_configuration_closes_catalog_connection(
    lake: Lakehouse, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake.db.execute("UPDATE config SET value='not json' WHERE key='format'")
    lake.db.commit()
    connections: list[sqlite3.Connection] = []
    original_connect = engine.connect

    def tracking_connect(root: Path) -> sqlite3.Connection:
        connection = original_connect(root)
        connections.append(connection)
        return connection

    monkeypatch.setattr(engine, "connect", tracking_connect)
    with pytest.raises(ValueError):
        Lakehouse(lake.root)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


@pytest.mark.parametrize(
    "corruption",
    [
        "empty",
        "missing-bucket",
        "missing-node",
        "extra-bucket",
        "extra-node",
        "wrong-format",
        "swapped-bucket",
        "node-nonobject",
        "missing-entry-metadata",
    ],
)
def test_invalid_manifest_cannot_prune_history_or_reclassify_live_files_as_orphans(
    lake: Lakehouse, tmp_path: Path, corruption: str
) -> None:
    first = lake.ingest(source(tmp_path, [event()]))
    latest = lake.ingest(source(tmp_path, [event(version=2)], name="updated.ndjson"))
    manifest = lake.manifest(latest)
    partitions = manifest["partitions"]
    if corruption == "empty":
        manifest["partitions"] = {}
    elif corruption == "missing-bucket":
        del partitions["1"]
    elif corruption == "missing-node":
        del partitions["0"]["facts"]
    elif corruption == "extra-bucket":
        partitions["2"] = partitions["0"]
    elif corruption == "extra-node":
        partitions["0"]["extra"] = partitions["0"]["facts"]
    elif corruption == "wrong-format":
        manifest["format_version"] = 99
    elif corruption == "swapped-bucket":
        partitions["1"] = partitions["0"]
    elif corruption == "node-nonobject":
        partitions["0"]["facts"] = None
    else:
        del partitions["0"]["facts"]["sha256"]
    lake.db.execute("UPDATE snapshots SET manifest=? WHERE id=?", (json.dumps(manifest), latest))
    lake.db.commit()
    (lake.root / "data" / "unpublished.parquet").write_bytes(b"orphan")
    before = {path.name: path.read_bytes() for path in (lake.root / "data").iterdir()}

    with pytest.raises(ValueError, match="manifest"):
        lake.validate(latest)
    with pytest.raises(ValueError, match="manifest"):
        with Snapshot(lake.root, latest) as pinned:
            list(pinned.rows())
    with pytest.raises(ValueError, match="manifest"):
        lake.build()
    for retain in (None, 1):
        with pytest.raises(ValueError, match="manifest"):
            recover(lake, retain=retain)
        assert lake.snapshots() == [first, latest]
        assert {path.name: path.read_bytes() for path in (lake.root / "data").iterdir()} == before
    assert lake.db.execute("SELECT count(*) FROM pins").fetchone()[0] == 0
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 2


def test_zero_row_snapshot_still_contains_the_complete_publication_graph(
    lake: Lakehouse, tmp_path: Path
) -> None:
    snapshot = lake.ingest(source(tmp_path, []))
    assert lake.validate(snapshot) == {"files": 6, "rows": 0}
    with Snapshot(lake.root, snapshot) as pinned:
        assert list(pinned.rows()) == []
        assert list(pinned.rows("daily")) == []
    assert recover(lake, retain=1)["removed_orphans"] == []
    assert lake.snapshots() == [snapshot]
