import importlib.util
import os
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "select_projects.py"
spec = importlib.util.spec_from_file_location("selection", MODULE)
assert spec and spec.loader
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


def test_all_manifest_identities():
    assert len(selection.load_projects()) == 10


def test_canonical_directory_alias_cannot_omit_a_project(monkeypatch):
    projects = deepcopy(selection.load_projects())
    next(p for p in projects if p["slug"] == "strata")["directory"] = (
        "projects/01-anchor/../01-anchor"
    )
    monkeypatch.setattr(selection.tomllib, "load", lambda stream: {"projects": projects})
    with pytest.raises(ValueError, match="duplicate directory"):
        selection.load_projects()


def test_added_modified_deleted_and_cross_project_rename():
    projects = selection.load_projects()
    for paths, expected in [
        (["projects/01-anchor/src/new.py"], {"anchor"}),
        (["projects/02-strata/src/changed.py"], {"strata"}),
        (["projects/03-current/deleted.py"], {"current"}),
        (["projects/01-anchor/old.py", "projects/02-strata/new.py"], {"anchor", "strata"}),
    ]:
        assert {p["slug"] for p in selection.select(paths, projects)} == expected


def test_shared_unknown_and_unavailable_base_select_all():
    projects = selection.load_projects()
    for paths in (
        None,
        ["ruff.toml"],
        [".github/workflows/ci.yml"],
        ["unknown/file"],
        ["README.md"],
    ):
        assert len(selection.select(paths, projects)) == 10
    assert selection.select([], projects) == []
    assert selection.diff_paths("not-a-revision", "HEAD") is None


def test_actual_rename_deleted_and_empty_diff(tmp_path):
    def git(*args):
        return (
            subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
            .stdout.decode()
            .strip()
        )

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "old.py").write_text("x=1\n")
    git("add", "old.py")
    git("commit", "-qm", "initial")
    base = git("rev-parse", "HEAD")
    (tmp_path / "old.py").rename(tmp_path / "new.py")
    git("add", "-A")
    git("commit", "-qm", "rename")
    assert set(selection.diff_paths(base, "HEAD", tmp_path)) == {"old.py", "new.py"}
    assert selection.diff_paths("HEAD", "HEAD", tmp_path) == []
    # Git permits byte paths that cannot be decoded as UTF-8 on the required POSIX runner.
    if os.name == "posix":
        (tmp_path / os.fsdecode(b"invalid-\xff.py")).write_text("x=2\n")
        git("add", "-A")
        git("commit", "-qm", "non UTF8 filename")
        assert selection.diff_paths("HEAD~1", "HEAD", tmp_path) is None
        assert len(selection.select(None, selection.load_projects())) == 10


def test_noncanonical_and_overlapping_paths_cannot_underselect(monkeypatch):
    projects = deepcopy(selection.load_projects())
    projects[0]["directory"] = "projects/./01-anchor"
    monkeypatch.setattr(selection.tomllib, "load", lambda stream: {"projects": projects})
    with pytest.raises(ValueError, match="canonical"):
        selection.load_projects()
    projects[0]["directory"] = "projects"
    with pytest.raises(ValueError, match="overlap"):
        selection.load_projects()


def test_git_option_is_not_accepted_as_a_revision():
    assert selection.diff_paths("--output=/tmp/portfolio-diff", "HEAD") is None
