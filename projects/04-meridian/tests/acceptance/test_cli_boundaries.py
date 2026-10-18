import json
from pathlib import Path

import pytest

from pp_meridian.cli import clean, output_directory


def test_output_requires_absolute_owned_external_directory(tmp_path):
    with pytest.raises(ValueError):
        output_directory("relative")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "user.txt").write_text("preserve")
    with pytest.raises(ValueError):
        output_directory(str(foreign))
    assert (foreign / "user.txt").read_text() == "preserve"
    link = tmp_path / "link"
    link.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError):
        output_directory(str(link))
    project = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError):
        output_directory(str(project))


def test_clean_requires_marker_and_rejects_forged_schema(tmp_path):
    output = tmp_path / "demo"
    output.mkdir()
    with pytest.raises(ValueError):
        clean(output)
    (output / ".meridian-owned.json").write_text(
        json.dumps(
            {
                "schema": "public",
                "database_sha256": "wrong",
                "files": ["demo.json", "report.html", "benchmark.json"],
            }
        )
    )
    with pytest.raises(ValueError):
        clean(output)


def test_public_demo_cleanup_drops_only_owned_schema_and_preserves_user_file(tmp_path):
    import os
    import subprocess
    import sys

    import psycopg

    output = tmp_path / "owned-demo"
    command = [sys.executable, "-m", "pp_meridian.cli"]
    result = subprocess.run(
        [*command, "demo", "--output", str(output), "--seed", "1729"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    marker = json.loads((output / ".meridian-owned.json").read_text())
    report = json.loads((output / "demo.json").read_text())
    assert report["duplicate_journal_identical"] and report["rebuild_consistent"]
    note = output / "user-note.txt"
    note.write_text("preserve this caller-created file")
    result = subprocess.run(
        [*command, "clean-demo", "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert note.read_text() == "preserve this caller-created file"
    assert not (output / "demo.json").exists()
    assert not (output / ".meridian-owned.json").exists()
    with psycopg.connect(os.environ["MERIDIAN_DATABASE_URL"]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM pg_namespace WHERE nspname=%s", [marker["schema"]]
            ).fetchone()[0]
            == 0
        )
