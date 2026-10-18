import importlib.util
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "select_projects.py"
spec = importlib.util.spec_from_file_location("selection", MODULE)
assert spec and spec.loader
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


def test_all_manifest_identities():
    assert len(selection.load_projects()) == 10


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
