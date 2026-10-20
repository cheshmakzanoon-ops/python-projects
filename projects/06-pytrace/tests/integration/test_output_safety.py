"""Read-only analysis and review previews must never replace selected source."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pp_pytrace.cache import analyze
from pp_pytrace.cli import main


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_cache_cannot_alias_analyzed_source(tmp_path: Path, alias: str) -> None:
    source = tmp_path / "service.py"
    before = b"import os\nos.system(input())\n"
    source.write_bytes(before)
    cache = source
    if alias == "symlink":
        cache = tmp_path / "cache.json"
        cache.symlink_to(source)
    elif alias == "hardlink":
        cache = tmp_path / "cache.json"
        os.link(source, cache)
    with pytest.raises(ValueError, match="overwrite selected source"):
        analyze(source, cache)
    assert source.read_bytes() == before


def test_cache_publication_does_not_follow_predictable_temporary(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    before = b"import os\nos.system(input())\n"
    source.write_bytes(before)
    cache = tmp_path / "cache.json"
    decoy = tmp_path / "cache.json.tmp"
    decoy.symlink_to(source)
    assert analyze(source, cache).diagnostics[0].rule_id == "PT001"
    assert source.read_bytes() == before
    assert decoy.is_symlink()
    assert analyze(source, cache).cache_hits == 1


def test_cache_publication_failure_removes_only_its_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "service.py"
    source.write_text("value = 1\n")
    cache = tmp_path / "cache.json"
    cache.write_text("old cache")
    unrelated = tmp_path / ".pytrace-cache-previous.tmp"
    unrelated.write_text("keep")

    def fail_replace(path: Path, destination: Path) -> Path:
        raise OSError("replacement failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        analyze(source, cache)
    assert cache.read_text() == "old cache"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        ".pytrace-cache-previous.tmp",
        "cache.json",
        "service.py",
    ]


@pytest.mark.parametrize(
    "command, flag", [("analyze", "--output"), ("diff", "--output"), ("diff", "--plan")]
)
@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_cli_outputs_cannot_replace_source(
    tmp_path: Path, command: str, flag: str, alias: str
) -> None:
    source = tmp_path / "service.py"
    before = b'value = str("example")\n'
    source.write_bytes(before)
    output = source
    if alias == "symlink":
        output = tmp_path / "output.json"
        output.symlink_to(source)
    elif alias == "hardlink":
        output = tmp_path / "output.json"
        os.link(source, output)
    arguments = [command, str(tmp_path)]
    if command == "diff":
        arguments.append(source.name)
    assert main([*arguments, flag, str(output)]) == 2
    assert source.read_bytes() == before


def test_diff_plan_and_patch_require_distinct_destinations(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    source.write_text('value = str("example")\n')
    output = tmp_path / "preview.json"
    assert (
        main(["diff", str(tmp_path), source.name, "--plan", str(output), "--output", str(output)])
        == 2
    )
    assert not output.exists()


def test_diff_output_cannot_overwrite_unselected_python_source(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    source.write_text('value = str("example")\n')
    unselected = tmp_path / "other.py"
    unselected.write_text("important = 42\n")
    assert main(["diff", str(tmp_path), source.name, "--plan", str(unselected)]) == 2
    assert unselected.read_text() == "important = 42\n"
