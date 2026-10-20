"""A verification clone must never reuse an editable environment from its caller."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("check", "xml", "expected"),
    [
        ("demo", None, 0),
        ("check", '<testsuite tests="1"><testcase name="executed"/></testsuite>', 0),
        (
            "check",
            '<testsuite tests="1" skipped="1"><testcase><skipped/></testcase></testsuite>',
            1,
        ),
        ("check", '<testsuite tests="0"/>', 1),
        ("check", None, 1),
    ],
)
def test_snapshot_isolates_environment_and_records_executed_results(
    tmp_path, monkeypatch, check, xml, expected
):
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
        f"report = {xml!r}\n"
        "if report is not None:\n"
        "    from pathlib import Path\n"
        "    Path(os.environ['PORTFOLIO_CHECK_REPORT']).write_text(report)\n"
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
        ["verify_snapshot.py", "--checks", check, "--output", str(output)],
    )
    assert snapshot.main() == expected
    report = json.loads((output / "current-3.13.16.json").read_text())
    assert report["status"] == ("passed" if expected == 0 else "failed")
    assert report["source_unchanged_after"]
    assert not report["source_dirty"]
    summary = json.loads((output / "verification.json").read_text())
    assert summary["status"] == report["status"]
    assert summary["source_commit"] == report["source_commit"]
    assert summary["requested_checks"] == [check]
    assert summary["requested_projects"] == ["current"]
    assert "current-3.13.16.json" in summary["reports"]
    for artifact in summary["artifacts"]:
        import hashlib

        path = output / artifact["path"]
        assert path.stat().st_size == artifact["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    if check == "check" and expected == 0:
        assert summary["tests"] == {"passed": 1, "failed": 0, "errors": 0, "skipped": 0}
