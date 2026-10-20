"""A verification clone must never reuse an editable environment from its caller."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def test_snapshot_isolates_an_inherited_project_environment(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("verify_snapshot", SCRIPTS / "verify_snapshot.py")
    assert spec and spec.loader
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    source = tmp_path / "repository"
    source.mkdir()
    (source / "portfolio.toml").write_text('[[projects]]\nslug="current"\ndirectory="project"\n')
    (source / "project").mkdir()
    (source / "project/uv.lock").write_text("version=1\n")
    (source / "scripts").mkdir()
    (source / "scripts/portfolio.py").write_text(
        "import os\n"
        "if any(name in os.environ for name in "
        "('UV_PROJECT_ENVIRONMENT','UV_PROJECT','UV_WORKING_DIR','PYTHONPATH','PYTHONHOME')):\n"
        "    raise SystemExit('verification reused caller environment')\n"
    )
    for arguments in (
        ["init", "-q"],
        ["config", "user.name", "Test"],
        ["config", "user.email", "test@example.invalid"],
        ["add", "."],
        ["commit", "-qm", "verification fixture"],
    ):
        subprocess.run(["git", *arguments], cwd=source, check=True, capture_output=True)
    output = tmp_path / "results"
    monkeypatch.setattr(snapshot, "ROOT", source)
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(tmp_path / "unrelated-environment"))
    for name in ("UV_PROJECT", "UV_WORKING_DIR", "PYTHONPATH", "PYTHONHOME"):
        monkeypatch.setenv(name, str(tmp_path / "unrelated-source"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_snapshot.py", "--checks", "demo", "--output", str(output)],
    )
    assert snapshot.main() == 0
    report = json.loads((output / "current-3.13.16.json").read_text())
    assert report["status"] == "passed"
    assert report["source_unchanged_after"]
    assert not report["source_dirty"]
