"""Public integration stages cannot reuse or replace a caller's selected environment."""

import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stages_pin_distinct_environments_and_resolve_supported_patch(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "integration_environment", ROOT / "integrations/run.py"
    )
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    source = tmp_path / "source"
    source.mkdir()
    (source / "portfolio.toml").write_bytes((ROOT / "portfolio.toml").read_bytes())
    with (source / "portfolio.toml").open("rb") as stream:
        projects = {p["slug"]: p for p in tomllib.load(stream)["projects"]}
    for slug, stage in runner.STAGES["stream-lake"]:
        project = projects[slug]
        (source / project["directory"]).mkdir(parents=True)
        path = source / "integrations" / stage
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import argparse,os\nfrom pathlib import Path\n"
            'p=argparse.ArgumentParser();p.add_argument("--output",type=Path);a=p.parse_args()\n'
            'assert "PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ\n'
            'assert os.environ["UV_PROJECT"] == str(Path.cwd())\n'
            'assert os.environ["UV_WORKING_DIR"] == str(Path.cwd())\n'
            f'assert os.environ["UV_PROJECT_ENVIRONMENT"] == {str(source / ".local/venvs" / (slug + "-3.13.16"))!r}\n'
            f'(a.output / "{slug}.txt").write_text("isolated")\n'
        )
    for arguments in (
        ["init", "-q"],
        ["config", "user.name", "Test"],
        ["config", "user.email", "test@example.invalid"],
        ["add", "."],
        ["commit", "-qm", "integration fixture"],
    ):
        subprocess.run(["git", *arguments], cwd=source, check=True, capture_output=True)
    shim = tmp_path / "bin"
    shim.mkdir()
    executable = shim / "uv"
    executable.write_text(
        f"#!{sys.executable}\nimport os,sys\n"
        'assert sys.argv[sys.argv.index("--python")+1] == "3.13.16"\n'
        'start=sys.argv.index("python")+1\n'
        "os.execv(sys.executable,[sys.executable,*sys.argv[start:]])\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(shim) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("PORTFOLIO_PYTHON", "3.13")
    for name in (
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        monkeypatch.setenv(name, str(tmp_path / "unrelated"))
    monkeypatch.setattr(runner, "ROOT", source)
    output = tmp_path / "result"
    monkeypatch.setattr(sys, "argv", ["run.py", "stream-lake", "--output", str(output)])
    assert runner.main() == 0
    report = json.loads((output / "integration.json").read_text())
    assert report["status"] == "passed"
    assert not report["source_dirty"]
    assert (output / "current.txt").read_text() == (output / "quarry.txt").read_text() == "isolated"


def test_nested_settlement_participant_has_its_own_environment(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "settlement_environment", ROOT / "integrations/01-settlement/meridian_stage.py"
    )
    assert spec and spec.loader
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    directory = tmp_path / "projects/01-anchor"
    directory.mkdir(parents=True)
    (directory / ".python-version").write_text("3.14.8\n")
    for name in (
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        monkeypatch.setenv(name, "foreign-meridian-environment")
    for version in ("3.13.16", "3.14.8"):
        environment = stage.anchor_environment(tmp_path, version)
        expected = (
            directory / ".venv" if version == "3.14.8" else tmp_path / ".local/venvs/anchor-3.13.16"
        )
        assert environment["UV_PROJECT_ENVIRONMENT"] == str(expected)
        assert environment["UV_PROJECT"] == environment["UV_WORKING_DIR"] == str(directory)
        assert environment["PORTFOLIO_PYTHON"] == version
        assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
