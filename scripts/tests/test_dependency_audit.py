"""Advisory-service and lock-export failures must never become passing audits."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).resolve().parents[1] / "audit_dependencies.py"
spec = importlib.util.spec_from_file_location("audit_dependencies", MODULE)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_audit_preserves_service_failure_and_records_exact_inputs(tmp_path, monkeypatch, exit_code):
    project = tmp_path / "project"
    project.mkdir()
    (project / "uv.lock").write_text("version=1\n")
    output = tmp_path / "reports"
    output.mkdir()
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "export" in command:
            (output / "current-requirements.txt").write_text("example==1.0 --hash=sha256:abc\n")
            return SimpleNamespace(returncode=0)
        (output / "current-audit.json").write_text(
            json.dumps({"dependencies": [{"name": "example", "version": "1.0", "vulns": []}]})
        )
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit.subprocess, "run", run)
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **k: '[["example","1.0"]]')
    result = audit.audit_project({"slug": "current", "directory": "project"}, output)
    assert result["status"] == ("passed" if exit_code == 0 else "failed")
    assert result["exit_code"] == exit_code
    assert result["report"] == "current-audit.json"
    assert len(result["lockfile_sha256"]) == 64
    assert "--locked" in calls[0] and "--no-dev" in calls[0]
    assert "--require-hashes" in calls[1] and "--disable-pip" in calls[1]


def test_stale_lock_does_not_audit_a_previous_export(tmp_path, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(audit.subprocess, "run", run)
    result = audit.audit_project({"slug": "current", "directory": "unused"}, tmp_path)
    assert result == {"project": "current", "status": "error", "stage": "locked export"}
    assert len(calls) == 1


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"dependencies": []},
        {"dependencies": [{"vulns": []}]},
        {"dependencies": [{"skip_reason": "unavailable"}]},
    ],
)
def test_missing_or_partial_report_cannot_pass(tmp_path, monkeypatch, data):
    (tmp_path / "uv.lock").write_text("version=1\n")

    def run(command, **kwargs):
        if "export" in command:
            (tmp_path / "current-requirements.txt").write_text("")
        elif data is not None:
            (tmp_path / "current-audit.json").write_text(json.dumps(data))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit.subprocess, "run", run)
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **k: '[["example","1.0"]]')
    assert (
        audit.audit_project({"slug": "current", "directory": "."}, tmp_path)["status"] == "failed"
    )


def test_empty_runtime_export_has_a_valid_empty_audit(tmp_path, monkeypatch):
    (tmp_path / "uv.lock").write_text("version=1\n")

    def run(command, **kwargs):
        if "export" in command:
            (tmp_path / "strata-requirements.txt").write_text("# No runtime dependencies\n")
        else:
            (tmp_path / "strata-audit.json").write_text('{"dependencies": []}')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit.subprocess, "run", run)
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **k: "[]")
    assert audit.audit_project({"slug": "strata", "directory": "."}, tmp_path)["status"] == "passed"


def test_export_identity_parser_evaluates_markers_and_canonicalizes_names(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# Export comment\nExample_Name==1.0 \\\n    --hash=sha256:abc\n"
        'other==2.0 ; python_version < "0" \\\n    --hash=sha256:def\n'
    )
    result = subprocess.check_output(
        [sys.executable, "-I", "-c", audit.EXPECTED_PACKAGES, str(requirements)], text=True
    )
    assert json.loads(result) == [["example-name", "1.0"]]
