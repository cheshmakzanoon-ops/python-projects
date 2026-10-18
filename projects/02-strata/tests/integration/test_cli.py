from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pp_strata.cli import clean_output, output_directory


def test_cli_demo_public_interface(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    process = subprocess.run(
        [sys.executable, "-m", "pp_strata.cli", "demo", "--output", str(output), "--seed", "1729"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads((output / "demo.json").read_text())
    assert report["status"] == "passed"
    assert all(report["checks"].values())
    assert report["acknowledged_transactions"] == 10
    assert (output / "timeline.txt").read_text().count("\n") == 5
    for command in ("inspect", "verify", "compact"):
        process = subprocess.run(
            [sys.executable, "-m", "pp_strata.cli", command, str(output / "catalog")],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert process.returncode == 0, process.stderr
    process = subprocess.run(
        [sys.executable, "-m", "pp_strata.cli", "clean-demo", "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 0, process.stderr
    assert not output.exists()


def test_cli_clean_safety_and_foreign_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        output_directory("relative")
    with pytest.raises(ValueError):
        clean_output("relative")
    (tmp_path / "foreign.txt").write_text("preserve")
    with pytest.raises(ValueError):
        output_directory(str(tmp_path))
    with pytest.raises(ValueError):
        clean_output(str(tmp_path))
    output = output_directory(str(tmp_path / "owned"))
    (output / "foreign.txt").write_text("preserve")
    clean_output(str(output))
    assert (output / "foreign.txt").read_text() == "preserve"
    output = output_directory(str(tmp_path / "owned-2"))
    (output / "catalog").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        clean_output(str(output))
    assert (tmp_path / "foreign.txt").read_text() == "preserve"


def test_reject_database_internal_symlink(tmp_path: Path) -> None:
    from pp_strata import Corruption, Database

    foreign = tmp_path / "foreign"
    foreign.write_text("preserve")
    database = tmp_path / "db"
    database.mkdir()
    (database / "WAL").symlink_to(foreign)
    with pytest.raises(Corruption):
        Database.open(database)
    assert foreign.read_text() == "preserve"
