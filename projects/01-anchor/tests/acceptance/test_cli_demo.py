"""A reviewer drives the installed CLI, not a second test-only implementation."""

import csv
import io
import json
import os
import subprocess
import sys
import zipfile


def test_AN01_AN03_real_export_cli_and_owned_cleanup(dsn, tmp_path):
    output = tmp_path / "demo"
    env = {**os.environ, "ANCHOR_DATABASE_URL": dsn}
    result = subprocess.run(
        [sys.executable, "-m", "pp_anchor.cli", "demo", "--output", str(output), "--seed", "1729"],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "history.json").read_text())
    assert report["status"] == "completed"
    assert report["worker_killed"] is True and report["replay_verified"] is True
    assert report["provider"] == {"publications": 1, "fenced": False}
    assert report["metrics"]["retries"] == 1
    with zipfile.ZipFile(output / "dataset.zip") as archive:
        rows = [
            row
            for name in archive.namelist()
            for row in csv.DictReader(io.StringIO(archive.read(name).decode()))
        ]
    assert len(rows) == 60
    assert sorted((int(r["id"]), int(r["value"])) for r in rows) == [(i, i * i) for i in range(60)]
    assert "activity_claimed" in (output / "timeline.txt").read_text()
    result = subprocess.run(
        [sys.executable, "-m", "pp_anchor.cli", "clean-demo", "--output", str(output)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not output.exists()
