import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pp_current import Config, Journal, canonical
from pp_current.cli import MARKER, app, clean_demo, execute, owned


def test_cli_demo_and_safe_cleanup(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    command = [sys.executable, "-m", "pp_current.cli"]
    completed = subprocess.run(
        [*command, "demo", "--output", str(output), "--seed", "1729"],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "report.json").read_text())
    assert report["oracle_matches"] and sum(report["dispositions"].values()) == 10_000
    assert (
        subprocess.run(
            [*command, "clean-demo", "--output", str(output)], capture_output=True, timeout=10
        ).returncode
        == 0
    )
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    (unowned / "keep").write_text("keep")
    assert (
        subprocess.run(
            [*command, "clean-demo", "--output", str(unowned)], capture_output=True, timeout=10
        ).returncode
        != 0
    )
    assert (unowned / "keep").read_text() == "keep"


def test_inspect_never_creates_missing_state(tmp_path: Path) -> None:
    output = tmp_path / "missing"
    result = CliRunner().invoke(app, ["inspect", "--output", str(output)])
    assert result.exit_code != 0
    assert not output.exists()


def test_inspect_does_not_initialize_unrelated_sqlite_database(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "current.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE keep(value TEXT)")
    db.close()
    before = path.read_bytes()
    result = CliRunner().invoke(app, ["inspect", "--output", str(tmp_path)])
    assert result.exit_code != 0
    assert path.read_bytes() == before


def test_inspect_reads_existing_checkpoint(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "current.sqlite")
    journal.publish(journal.recover(Config((canonical(["s", 0]),))))
    journal.close()
    result = CliRunner().invoke(app, ["inspect", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_ownership_marker_symlink_is_never_followed(tmp_path: Path) -> None:
    outside = tmp_path / "keep"
    outside.write_text("private state")
    output = tmp_path / "output"
    output.mkdir()
    (output / MARKER).symlink_to(outside)
    with pytest.raises(ValueError, match="ownership|symlink"):
        owned(output)
    with pytest.raises(ValueError, match="ownership|symlink|unowned"):
        clean_demo(output)
    assert outside.read_text() == "private state"


def test_cleanup_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    real = tmp_path / "real"
    output = real / "demo"
    owned(output)
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        clean_demo(alias / "demo")
    assert output.is_dir()


def test_execute_rejects_existing_report_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "keep"
    outside.write_text("private state")
    output = tmp_path / "output"
    owned(output)
    (output / "report.json").symlink_to(outside)
    with pytest.raises(ValueError, match="fresh|contains state"):
        execute(output, 1, 1729)
    assert outside.read_text() == "private state"
    assert not (output / "current.sqlite").exists()


def test_replay_requires_fresh_output_and_preserves_existing_state(tmp_path: Path) -> None:
    from pp_current import Record

    output = tmp_path / "output"
    owned(output)
    existing = output / "keep"
    existing.write_text("private state")
    source = tmp_path / "input.ndjson"
    source.write_text(Record("s", 0, 0, kind="end").wire() + "\n")
    result = CliRunner().invoke(app, ["replay", "--output", str(output), "--input", str(source)])
    assert result.exit_code != 0
    assert existing.read_text() == "private state"
    assert not (output / "current.sqlite").exists()
