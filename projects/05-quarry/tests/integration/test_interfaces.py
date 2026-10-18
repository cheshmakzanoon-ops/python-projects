from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from pp_quarry import Config, Contract, Event, Field, Lakehouse, Snapshot, recover
from pp_quarry.cli import clean_output, demo, main
from pp_quarry.lineage import explain
from tests.conftest import event, source


def test_csv_nullable_projection_and_public_commands(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    path = tmp_path / "events.csv"
    with path.open("w") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["source_namespace", "key", "version", "operation", "payload"]
        )
        writer.writeheader()
        row = event()
        row["payload"] = json.dumps(row["payload"])
        writer.writerow(row)
    lake.ingest(path)
    assert explain(lake, "devices", "x")["versions"][0]["offset"] == 1
    for command in ("snapshots", "explain", "validate", "recover", "build", "query"):
        monkeypatch.setattr("sys.argv", ["quarry", command, "--dataset", str(lake.root)])
        main()
        assert json.loads(capsys.readouterr().out) is not None
    monkeypatch.setattr(
        "sys.argv",
        ["quarry", "lineage", "--dataset", str(lake.root), "--namespace", "devices", "--key", "x"],
    )
    main()
    assert json.loads(capsys.readouterr().out)["key"] == "x"
    for command in ("plan", "ingest"):
        monkeypatch.setattr(
            "sys.argv", ["quarry", command, "--dataset", str(lake.root), "--source", str(path)]
        )
        main()
        assert json.loads(capsys.readouterr().out)
    lake.ingest(
        source(tmp_path, [event("y", firmware="new")]),
        Contract({**Contract().fields, "firmware": Field("string", True)}),
    )
    with Snapshot(lake.root) as pinned:
        rows = list(pinned.rows())
        assert rows[0]["payload__firmware"] is None
        assert rows[1]["payload__firmware"] == "new"
        assert list(pinned.rows("normalized", limit=1))[0]["operation"] == "upsert"
        with pytest.raises(ValueError):
            list(pinned.rows("arbitrary"))
    with pytest.raises(ValueError, match="closed"):
        list(pinned.rows())


def test_limits_ownership_malformed_fields_and_corrupt_files(
    lake: Lakehouse, tmp_path: Path
) -> None:
    with pytest.raises(ValueError):
        Event.from_dict({"key": "x"})
    for event_args in [
        ("", "x", 1, "delete", {}),
        ("n", "x", 1, "unknown", {}),
        ("n", "x", 1, "upsert", []),
    ]:
        with pytest.raises(ValueError):
            Event(*event_args)  # type: ignore[arg-type]
    for payload in [
        {"device": "x", "day": "2026-01-01"},
        {"device": 1, "day": "2026-01-01", "value": 2},
    ]:
        with pytest.raises(ValueError):
            lake.ingest(source(tmp_path, [{**event(), "payload": payload}]))
    path = source(tmp_path, [{**event(), "key": "x" * 5000}])
    with pytest.raises(ValueError, match="memory"):
        lake.ingest(path)
    path.write_text("[]\n")
    with pytest.raises(ValueError, match="object"):
        lake.ingest(path)
    with pytest.raises(ValueError):
        lake.ingest(path, fault="invalid")
    with pytest.raises(ValueError):
        recover(lake, retain=0)
    snapshot = lake.ingest(source(tmp_path, [event()]))
    path = lake.root / lake.manifest(snapshot)["partitions"]["0"]["facts"]["path"]
    path.write_bytes(b"broken parquet")
    with pytest.raises(ValueError, match="checksum"):
        lake.validate(snapshot)
    with pytest.raises(ValueError):
        Lakehouse(lake.root, Config(buckets=4))
    other = tmp_path / "other"
    other.mkdir()
    (other / "user-file").touch()
    with pytest.raises(ValueError, match="empty or owned"):
        Lakehouse(other)
    with pytest.raises(ValueError):
        Snapshot(lake.root, 999999)
    (lake.root / "data" / "unexpected.txt").touch()
    with pytest.raises(ValueError, match="unexpected"):
        recover(lake)


def test_dataset_quality_upper_bounds_and_schema_diagnostics(
    lake: Lakehouse, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="maximum"):
        lake.ingest(source(tmp_path, [event(value=8)]), Contract(maximum=5))
    lake.ingest(source(tmp_path, [event(value=8)]))
    with pytest.raises(ValueError, match="dataset maximum"):
        lake.ingest(source(tmp_path, [], "empty.ndjson"), Contract(maximum=5))
    with pytest.raises(ValueError, match="row-count"):
        lake.ingest(source(tmp_path, [], "empty.ndjson"), Contract(min_rows=2))
    with pytest.raises(ValueError, match="undeclared"):
        lake.ingest(source(tmp_path, [event("other", unknown=1)]))
    for value in ({"fields": []}, {"fields": {"x": []}}):
        with pytest.raises(ValueError):
            Contract.from_dict(value)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Contract(min_rows=-1)
    with pytest.raises(ValueError):
        Contract({"x": Field("integer")}).validate(Event("n", "x", 1, "upsert", {"x": 2**80}))


def test_owned_demo_cleanup_and_report(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    report = demo(output, 1729)
    assert all(report["correctness_checks"].values())
    with pytest.raises(ValueError, match="already"):
        demo(output, 1729)
    (output / "private.txt").touch()
    with pytest.raises(ValueError, match="unexpected"):
        clean_output(output)
    (output / "private.txt").unlink()
    clean_output(output)
    assert not output.exists()
    with pytest.raises(ValueError, match="ownership"):
        clean_output(tmp_path)


def test_format_and_strict_config_migration_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for data in (
        {"fields": {"x": {"kind": "string", "nullable": "false"}}},
        {"fields": {}, "min_rows": "1"},
        {"fields": {}, "minimum": "bad"},
    ):
        with pytest.raises(ValueError):
            Contract.from_dict(data)  # type: ignore[arg-type]
    root = tmp_path / "lake"
    with Lakehouse(root) as lake:
        stored = json.loads(
            lake.db.execute("SELECT value FROM config WHERE key='format'").fetchone()[0]
        )
        stored["format_version"] = 999
        lake.db.execute("UPDATE config SET value=? WHERE key='format'", (json.dumps(stored),))
        lake.db.commit()
    with pytest.raises(ValueError, match="unsupported stored format"):
        Lakehouse(root)
    output = tmp_path / "demo"
    output.mkdir()
    (output / ".quarry-demo").touch()
    alias = tmp_path / "alias"
    alias.symlink_to(output, target_is_directory=True)
    monkeypatch.setattr("sys.argv", ["quarry", "clean-demo", "--output", str(alias)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert output.exists()


def test_arbitrary_payload_json_projection_retains_scalar_and_object(
    lake: Lakehouse, tmp_path: Path
) -> None:
    contract = Contract(
        {"aggregate": Field("json"), "as_json": Field("json"), "a/b": Field("string")}
    )
    payload = {"aggregate": {"count": 7, "revision": 3}, "as_json": "hello", "a/b": "literal-path"}
    lake.ingest(source(tmp_path, [{**event(), "payload": payload}]), contract)
    with Snapshot(lake.root) as view:
        row = next(view.rows())
        assert json.loads(row["payload"]) == payload
        assert json.loads(row["payload__aggregate"]) == payload["aggregate"]
        assert json.loads(row["payload__as_json"]) == "hello"
        assert row["payload__a/b"] == "literal-path"


@pytest.mark.parametrize(
    "contents,message",
    [
        ("x" * 5000 + "\n", "memory limit"),
        (
            "key,version,operation,payload\n" + ",".join("x" for _ in range(3000)) + "\n",
            "memory limit",
        ),
        ('key,version,operation,payload\n"x\ny",1,delete,{}\n', "multiline"),
        ("key,key,version,operation,payload\n", "unique"),
        ("key,version,operation,payload\nx,1,delete,{},extra\n", "width"),
    ],
)
def test_csv_total_record_and_header_bounds(
    lake: Lakehouse, tmp_path: Path, contents: str, message: str
) -> None:
    path = tmp_path / "bounded.csv"
    path.write_text(contents)
    with pytest.raises(ValueError, match=message):
        lake.ingest(path)
    assert lake.snapshots() == []
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 0


def test_source_mutate_and_restore_detects_exact_consumed_bytes(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pp_quarry.execution import engine

    path = source(tmp_path, [event(value=3)])
    original = path.read_bytes()
    real_read = engine.read

    def swapping(path: Path, size: int, *, observe: Any = None) -> Any:
        path.write_bytes(original.replace(b'"value": 3', b'"value": 4'))
        try:
            yield from real_read(path, size, observe=observe)
        finally:
            path.write_bytes(original)

    monkeypatch.setattr(engine, "read", swapping)
    with pytest.raises(ValueError, match="changed while reading"):
        lake.ingest(path)
    assert path.read_bytes() == original
    assert not lake.snapshots()
    assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == 0


def test_source_rewrite_during_build_cannot_advance_checkpoint(
    lake: Lakehouse, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = source(tmp_path, [event()])
    execute = lake._execute

    def rewriting(plan: Any, dag: Any) -> Any:
        manifest = execute(plan, dag)
        path.write_text(path.read_text().replace('"value": 3', '"value": 4'))
        return manifest

    monkeypatch.setattr(lake, "_execute", rewriting)
    with pytest.raises(ValueError, match="before publication"):
        lake.ingest(path)
    assert not lake.snapshots()
    assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == 0
    assert recover(lake)["removed_orphans"]


def test_pinned_query_uses_publication_memory_and_owned_spill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import duckdb

    root = tmp_path / "lake"
    with Lakehouse(
        root, Config(buckets=2, memory_mb=64, batch_size=8, max_record_bytes=4096)
    ) as lake:
        lake.ingest(source(tmp_path, [event()]))
        assert lake.manifest()["execution_settings"]["memory_mb"] == 64
    original = duckdb.connect
    statements: list[str] = []

    class Recorder:
        def __init__(self) -> None:
            self.connection = original()

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            self.connection.close()

        def execute(self, sql: str, *args: Any) -> Any:
            statements.append(sql)
            return self.connection.execute(sql, *args)

    monkeypatch.setattr(duckdb, "connect", Recorder)
    with Snapshot(root) as pinned:
        assert next(pinned.rows())["value"] == 3
    assert "SET memory_limit='64MB'" in statements
    assert any(
        str(root / "tmp") in sql and sql.startswith("SET temp_directory=") for sql in statements
    )
