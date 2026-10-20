"""Regression checks for failure propagation and subprocess ownership."""

import importlib.util
import os
import sys
import time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "portfolio.py"
spec = importlib.util.spec_from_file_location("portfolio", MODULE)
assert spec and spec.loader
portfolio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portfolio)


def test_exit_status_preserved(tmp_path):
    assert portfolio.execute([sys.executable, "-c", "raise SystemExit(23)"], tmp_path) == 23


def test_missing_executable_is_failure(tmp_path):
    assert portfolio.execute([str(tmp_path / "missing-executable")], tmp_path) == 1


def test_timeout_terminates_child_process_group(tmp_path):
    if os.name != "posix":
        return  # POSIX process-group semantics are verified on the required Linux runner.
    pidfile = tmp_path / "pid"
    child = "import time; time.sleep(120)"
    parent = (
        "import subprocess,sys,time; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c',sys.argv[2]]); "
        "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(120)"
    )
    assert (
        portfolio.execute([sys.executable, "-c", parent, str(pidfile), child], tmp_path, timeout=1)
        == 1
    )
    pid = int(pidfile.read_text())
    for _ in range(40):
        status = Path(f"/proc/{pid}/status")
        if not status.exists() or "\nState:\tZ" in status.read_text():
            break
        time.sleep(0.05)
    else:
        raise AssertionError("timeout left a running child process")


def test_cleanup_targets_same_owned_directory_as_demo(monkeypatch):
    calls = []

    def execute(command, cwd, timeout=600):
        calls.append((command, cwd))
        return 0

    monkeypatch.setattr(portfolio, "execute", execute)
    project = next(p for p in portfolio.manifest() if p["slug"] == "current")
    assert portfolio.project_task("clean-demo", project) == 0
    arguments = calls[0][0]
    assert arguments[arguments.index("--output") + 1] == str(portfolio.ROOT / ".local/current/demo")
    assert "--seed" not in arguments


def test_finished_parent_cannot_leave_running_descendant(tmp_path):
    if os.name != "posix":
        return
    pidfile = tmp_path / "pid"
    parent = (
        "import subprocess,sys; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); "
        "Path(sys.argv[1]).write_text(str(p.pid))"
    )
    assert portfolio.execute([sys.executable, "-c", parent, str(pidfile)], tmp_path) == 0
    pid = int(pidfile.read_text())
    for _ in range(40):
        status = Path(f"/proc/{pid}/status")
        if not status.exists() or "\nState:\tZ" in status.read_text():
            break
        time.sleep(0.05)
    else:
        raise AssertionError("finished command left a running descendant")


def test_task_uses_one_explicit_interpreter_for_run_build_and_wheel(monkeypatch):
    calls = []
    monkeypatch.delenv("PORTFOLIO_PYTHON", raising=False)
    monkeypatch.setattr(portfolio, "execute", lambda command, *args: calls.append(command) or 0)
    project = next(p for p in portfolio.manifest() if p["slug"] == "current")
    assert portfolio.project_task("check", project) == 0
    for command in calls[:-1]:
        assert command[command.index("--python") + 1] == project["default_python"]
    assert calls[-1][-1] == project["default_python"]
    calls.clear()
    monkeypatch.setenv("PORTFOLIO_PYTHON", "3.13.16")
    assert portfolio.project_task("check", project) == 0
    for command in calls[:-1]:
        assert command[command.index("--python") + 1] == "3.13.16"
    assert calls[-1][-1] == "3.13.16"
