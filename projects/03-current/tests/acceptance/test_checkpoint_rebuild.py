"""The documented inspection/replay commands rebuild incompatible checkpoints safely."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pp_current import Config, Journal, Record, Runtime, canonical
from pp_current.cli import app
from pp_current.runtime.engine import CODE_VERSION


def test_read_only_export_and_streaming_replay_preserve_configuration_and_old_state(
    tmp_path: Path,
) -> None:
    original = tmp_path / "old"
    config = Config(
        (canonical(["b", 0]), canonical(["a", 0])), size=10, slide=5, lateness=2, join_interval=3
    )
    journal = Journal(original / "current.sqlite")
    trace = [
        Record("a", 0, 0, 1, "key", 3),
        Record("a", 0, 1, 10, kind="watermark"),
        Record("b", 0, 0, kind="idle"),
        Record("a", 0, 2, kind="end"),
        Record("b", 0, 1, kind="resume"),
        Record("b", 0, 2, 9, "key", 4),
        Record("b", 0, 3, kind="end"),
    ]
    try:
        journal.admit(trace)
        asyncio.run(Runtime(journal, journal.recover(config, job_id="old-job")).run())
        raw = journal.db.execute("SELECT state FROM checkpoint").fetchone()[0]
        previous = json.loads(raw)
        previous["version"] = "current-2"
        journal.db.execute("UPDATE checkpoint SET state=?", (canonical(previous),))
    finally:
        journal.close()
    before = (original / "current.sqlite").read_bytes()
    journal = Journal(original / "current.sqlite", read_only=True)
    try:
        with pytest.raises(ValueError, match="incompatible"):
            journal.recover(config)
    finally:
        journal.close()
    runner = CliRunner()
    exported = runner.invoke(app, ["inspect", "--output", str(original), "--ingress"])
    assert exported.exit_code == 0, exported.output
    assert exported.output.splitlines() == [record.wire() for record in trace]
    saved = runner.invoke(app, ["inspect", "--output", str(original), "--config"])
    assert saved.exit_code == 0, saved.output
    input_path, config_path = tmp_path / "ingress.ndjson", tmp_path / "config.json"
    input_path.write_text(exported.output)
    config_path.write_text(saved.output)
    rebuilt = tmp_path / "new"
    result = runner.invoke(
        app,
        [
            "replay",
            "--input",
            str(input_path),
            "--config",
            str(config_path),
            "--job-id",
            "reconciled-v3",
            "--output",
            str(rebuilt),
        ],
    )
    assert result.exit_code == 0, result.output
    journal = Journal(rebuilt / "current.sqlite", read_only=True)
    try:
        engine = journal.recover(config, job_id="reconciled-v3")
        assert engine.position == len(trace)
        assert engine.dispositions["accepted-late"] == 1
        assert all(row["job_id"] == "reconciled-v3" for row in journal.export())
        assert any(row["payload"]["sum"] == 7 for row in journal.export())  # type: ignore[index]
        assert (
            json.loads(journal.db.execute("SELECT state FROM checkpoint").fetchone()[0])["version"]
            == CODE_VERSION
        )
    finally:
        journal.close()
    assert (original / "current.sqlite").read_bytes() == before


def test_cli_replay_refuses_to_invent_an_application_transform(tmp_path: Path) -> None:
    from dataclasses import asdict

    config = replace(Config((canonical(["s", 0]),)), pipeline_version="temperature-c-v2")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(config)))
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "--config",
            str(path),
            "--input",
            str(tmp_path / "unused"),
            "--output",
            str(tmp_path / "new"),
        ],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "new").exists()


def test_replay_admits_large_inputs_in_bounded_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input.ndjson"
    with source.open("w") as stream:
        for offset in range(2000):
            stream.write(Record("s", 0, offset, offset, "key", 1).wire() + "\n")
        stream.write(Record("s", 0, 2000, kind="end").wire() + "\n")
    sizes = []
    admit = Journal.admit

    def bounded(self: Journal, records: list[Record]) -> list[Record]:
        sizes.append(len(records))
        return admit(self, records)

    monkeypatch.setattr(Journal, "admit", bounded)
    output = tmp_path / "new"
    result = CliRunner().invoke(app, ["replay", "--input", str(source), "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert sizes == [1000, 1000, 1]
    journal = Journal(output / "current.sqlite", read_only=True)
    try:
        assert journal.recover(Config((canonical(["s", 0]),))).position == 2001
        assert all(row["payload"]["count"] == 2000 for row in journal.export())  # type: ignore[index]
    finally:
        journal.close()
