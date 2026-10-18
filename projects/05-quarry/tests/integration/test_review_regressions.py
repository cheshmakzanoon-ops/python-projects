from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from pp_quarry import Contract, Field, Lakehouse, Snapshot
from tests.conftest import event, source


def test_snapshot_open_does_not_initialize_an_unowned_directory(tmp_path: Path) -> None:
    for root in (tmp_path / "absent", tmp_path / "empty", tmp_path / "user-files"):
        if root.name != "absent":
            root.mkdir()
        if root.name == "user-files":
            (root / "notes.txt").write_text("keep me")
        before = sorted(root.iterdir()) if root.exists() else None
        with pytest.raises(ValueError, match="owned"):
            Snapshot(root)
        assert (sorted(root.iterdir()) if root.exists() else None) == before


@pytest.mark.parametrize(
    "path_kind", ["absolute", "parent", "symlink", "data-symlink", "glob", "literal-glob"]
)
def test_queries_reject_manifest_paths_outside_owned_data(
    lake: Lakehouse, tmp_path: Path, path_kind: str
) -> None:
    snapshot = lake.ingest(source(tmp_path, [event()]))
    manifest = lake.manifest(snapshot)
    entry = manifest["partitions"]["0"]["facts"]
    external = tmp_path / "external.parquet"
    shutil.copyfile(lake.root / entry["path"], external)
    if path_kind == "absolute":
        entry["path"] = str(external)
    elif path_kind == "parent":
        entry["path"] = "../external.parquet"
    elif path_kind == "symlink":
        (lake.root / "data" / "linked.parquet").symlink_to(external)
        entry["path"] = "data/linked.parquet"
    elif path_kind in {"glob", "literal-glob"}:
        entry["path"] = "data/facts-*.parquet"
        if path_kind == "literal-glob":
            shutil.copyfile(external, lake.root / entry["path"])
    else:
        (lake.root / "data").rename(lake.root / "real-data")
        (lake.root / "data").symlink_to(lake.root / "real-data", target_is_directory=True)
    lake.db.execute("UPDATE snapshots SET manifest=? WHERE id=?", (json.dumps(manifest), snapshot))
    lake.db.commit()
    with pytest.raises(ValueError, match="owned|symlink"):
        with Snapshot(lake.root, snapshot) as pinned:
            list(pinned.rows())
    with pytest.raises(ValueError, match="owned|symlink"):
        lake.validate(snapshot)
    with pytest.raises(ValueError, match="owned|symlink"):
        lake.build()
    assert lake.snapshots() == [snapshot]
    assert external.is_file()


def test_nullable_json_columns_use_sql_null_and_preserve_json_string(
    lake: Lakehouse, tmp_path: Path
) -> None:
    contract = Contract({**Contract().fields, "extra": Field("json", True)})
    lake.ingest(
        source(
            tmp_path, [event("missing"), event("null", extra=None), event("text", extra="null")]
        ),
        contract,
    )
    with Snapshot(lake.root) as pinned:
        rows = {row["key"]: row for row in pinned.rows()}
    assert rows["missing"]["payload__extra"] is None
    assert rows["null"]["payload__extra"] is None
    assert json.loads(rows["text"]["payload__extra"]) == "null"


def test_number_overflow_rejects_entire_batch_without_checkpoint(
    lake: Lakehouse, tmp_path: Path
) -> None:
    contract = Contract({**Contract().fields, "temperature": Field("number")})
    with pytest.raises(ValueError, match="finite|range"):
        lake.ingest(
            source(
                tmp_path, [event("valid", temperature=1), event("overflow", temperature=10**400)]
            ),
            contract,
        )
    assert not lake.snapshots()
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 0
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 0
    lake.ingest(source(tmp_path, [event(temperature=10**300)]), contract)
    with Snapshot(lake.root) as pinned:
        assert math.isfinite(next(pinned.rows())["payload__temperature"])


def test_case_colliding_projection_columns_need_explicit_migration() -> None:
    with pytest.raises(ValueError, match="case|collid"):
        Contract({"firmware": Field("string"), "FIRMWARE": Field("string")})


def test_domain_and_extra_column_names_have_distinct_projections(
    lake: Lakehouse, tmp_path: Path
) -> None:
    contract = Contract({**Contract().fields, "DEVICE": Field("string")})
    lake.ingest(source(tmp_path, [event(DEVICE="upper")]), contract)
    with Snapshot(lake.root) as pinned:
        row = next(pinned.rows())
    assert row["device"] == "x"
    assert row["payload__DEVICE"] == "upper"


@pytest.mark.parametrize("name", ["catalog.sqlite-wal", "catalog.sqlite-shm"])
def test_catalog_sidecars_cannot_be_symlinks(tmp_path: Path, name: str) -> None:
    root = tmp_path / "lake"
    with Lakehouse(root):
        pass
    external = tmp_path / "external"
    external.write_text("keep me")
    (root / name).symlink_to(external)
    for constructor in (Lakehouse, Snapshot):
        with pytest.raises(ValueError, match="symlink"):
            constructor(root)
    assert external.read_text() == "keep me"


def test_nullable_day_accepts_explicit_null(lake: Lakehouse, tmp_path: Path) -> None:
    contract = Contract({**Contract().fields, "day": Field("string", True)})
    row = event()
    row["payload"]["day"] = None
    lake.ingest(source(tmp_path, [row]), contract)
    with Snapshot(lake.root) as pinned:
        assert next(pinned.rows())["day"] is None
