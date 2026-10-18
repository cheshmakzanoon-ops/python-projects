from __future__ import annotations

import json
from pathlib import Path

import pytest

from pp_pytrace.cache import analyze
from pp_pytrace.frontend.discovery import Limits, ParseFailure, discover, parse
from pp_pytrace.reporting.sarif import sarif, validate
from pp_pytrace.rules.registry import Config


def signature(root: Path, cache: Path | None = None) -> list[dict[str, object]]:
    return [item.to_dict() for item in analyze(root, cache).diagnostics]


def test_dependency_edit_and_local_edit_equal_clean(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "base.py").write_text("value=1\n")
    (root / "consumer.py").write_text("from base import value\nimport os\nos.system(input())\n")
    (root / "unrelated.py").write_text("other=2\n")
    cache = tmp_path / "cache.json"
    first = analyze(root, cache)
    assert len(first.invalidated) == 3
    assert analyze(root, cache).cache_hits == 3
    (root / "base.py").write_text("value=2\n")
    incremental = analyze(root, cache)
    assert set(incremental.invalidated) == {"base.py", "consumer.py"}
    assert signature(root, cache) == signature(root)
    (root / "consumer.py").write_text('from base import value\nimport os\nos.system("safe")\n')
    assert analyze(root, cache).invalidated == ("consumer.py",)
    assert signature(root, cache) == signature(root)


def test_relative_dependencies_cycles_and_config(tmp_path: Path) -> None:
    root = tmp_path / "source"
    package = root / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "a.py").write_text("from . import b\nvalue=1\n")
    (package / "b.py").write_text("from .a import value\n")
    cache = tmp_path / "cache.json"
    analyze(root, cache)
    (package / "a.py").write_text("from . import b\nvalue=2\n")
    assert set(analyze(root, cache).invalidated) == {"pkg/a.py", "pkg/b.py"}
    assert len(analyze(root, cache, Config(sources=("user_input",))).invalidated) == 3


def test_deleted_dependency_invalidates_consumer(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value=1\n")
    (tmp_path / "b.py").write_text("import a\n")
    cache = tmp_path / "cache.json"
    analyze(tmp_path, cache)
    (tmp_path / "a.py").unlink()
    assert analyze(tmp_path, cache).invalidated == ("b.py",)


def test_corrupted_cache_recovers(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1\n")
    cache = tmp_path / "cache.json"
    cache.write_text("{broken")
    assert analyze(tmp_path, cache).invalidated == ("a.py",)


@pytest.mark.parametrize(
    "document",
    [
        [],
        None,
        {"entries": []},
        {"entries": {"a.py": None}},
        {"entries": {"a.py": {"dependencies": [1]}}},
    ],
)
def test_cache_structure_corruption_is_a_cache_miss(tmp_path: Path, document: object) -> None:
    (tmp_path / "a.py").write_text("import os\nos.system(input())\n")
    cache = tmp_path / "cache.json"
    analyze(tmp_path, cache)
    if isinstance(document, dict):
        original = json.loads(cache.read_text())
        original.update(document)
        document = original
    cache.write_text(json.dumps(document))
    result = analyze(tmp_path, cache)
    assert result.invalidated == ("a.py",)
    assert result.cache_hits == 0
    assert [item.rule_id for item in result.diagnostics] == ["PT001"]


def test_corrupted_cached_diagnostic_rebuilds_analysis(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import os\nos.system(input())\n")
    cache = tmp_path / "cache.json"
    analyze(tmp_path, cache)
    document = json.loads(cache.read_text())
    document["entries"]["a.py"]["diagnostics"][0]["location"]["line"] = "broken"
    cache.write_text(json.dumps(document))
    result = analyze(tmp_path, cache)
    assert result.invalidated == ("a.py",)
    assert result.diagnostics[0].location.line == 2


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("rule_id", "PT999"),
        ("severity", "garbage"),
        ("confidence", "certain"),
        ("coverage", "safe"),
    ],
)
def test_cached_diagnostic_rejects_unknown_metadata(
    tmp_path: Path, field: str, invalid: str
) -> None:
    (tmp_path / "a.py").write_text("import os\nos.system(input())\n")
    cache = tmp_path / "cache.json"
    expected = analyze(tmp_path, cache).diagnostics
    document = json.loads(cache.read_text())
    document["entries"]["a.py"]["diagnostics"][0][field] = invalid
    cache.write_text(json.dumps(document))
    result = analyze(tmp_path, cache)
    assert result.invalidated == ("a.py",)
    assert result.cache_hits == 0
    assert result.diagnostics == expected
    assert analyze(tmp_path, cache).cache_hits == 1


def test_encoding_syntax_and_official_sarif(tmp_path: Path) -> None:
    (tmp_path / "latin.py").write_bytes(
        "# coding: latin-1\nimport os\nnaïve=input()\nos.system(naïve)\n".encode("latin-1")
    )
    (tmp_path / "broken.py").write_text("def broken(:\n")
    result = analyze(tmp_path)
    assert result.parse_failures == 1
    assert {item.rule_id for item in result.diagnostics} == {"PT001", "PT901"}
    document = sarif(result.diagnostics)
    validate(document)
    assert document == sarif(analyze(tmp_path).diagnostics)
    assert document["runs"][0]["columnKind"] == "unicodeCodePoints"
    invalid = json.loads(json.dumps(document))
    invalid["version"] = "9.0"
    with pytest.raises(Exception):
        validate(invalid)


def test_no_target_or_executable_configuration_runs(tmp_path: Path) -> None:
    sentinel = tmp_path / "MUST_NOT_EXIST"
    payload = f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("executed")\n'
    for name in ("__init__.py", "setup.py", "conftest.py", "target.py"):
        (tmp_path / name).write_text(payload)
    (tmp_path / "pytrace_config.py").write_text(payload)
    assert analyze(tmp_path).files == 5
    assert not sentinel.exists()


def test_parse_limits_timeout_count_memory_and_compile() -> None:
    with pytest.raises(ParseFailure, match="byte limit"):
        parse("x=1\n" * 20, limits=Limits(max_bytes=10))
    with pytest.raises(ParseFailure, match="node limit"):
        parse("x=1\n" * 20, limits=Limits(max_nodes=5))
    with pytest.raises(ParseFailure, match="timeout"):
        parse("x=1\n", limits=Limits(timeout_seconds=0.00001))
    with pytest.raises(ParseFailure):
        parse("x=1\n", limits=Limits(memory_bytes=1_000_000))
    with pytest.raises(ParseFailure):
        parse("return 1\n")


def test_file_count_exclusion_and_symlink_guard(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.py").write_text("x=1\n")
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "ignored.py").write_text("x=1\n")
    assert len(discover(tmp_path)) == 2
    with pytest.raises(ValueError, match="file count"):
        discover(tmp_path, limits=Limits(max_files=1))
    (tmp_path / "link.py").symlink_to(tmp_path / "a.py")
    with pytest.raises(ValueError, match="symlink"):
        discover(tmp_path)


def test_source_read_is_bounded_before_allocation_and_growth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from pp_pytrace.frontend.discovery import read_bounded

    path = tmp_path / "growing.py"
    path.write_bytes(b"x")
    requests: list[int] = []

    class GuardedStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            assert size == 11  # growth is stopped at max_bytes+1, never read-all
            requests.append(size)
            return super().read(size)

    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: GuardedStream(b"x" * 100))
    with pytest.raises(ParseFailure, match="byte limit"):
        read_bounded(path, 10)
    assert requests == [11]


def test_oversized_source_does_not_read_bytes_after_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "giant.py"
    source.write_bytes(b"x" * 100)
    original_read = Path.read_bytes

    def guarded_read(path: Path) -> bytes:
        assert path != source, "oversized rejected source must never be read_bytes()"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    result = analyze(tmp_path, limits=Limits(max_bytes=10))
    assert result.parse_failures == 1
    assert "byte limit" in result.diagnostics[0].message


def test_discovery_ignores_directories_named_with_python_suffix(tmp_path: Path) -> None:
    package = tmp_path / "nested.py"
    package.mkdir()
    (package / "module.py").write_text("x=1\n")
    assert analyze(tmp_path).files == 1


def test_explicit_symlink_source_root_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "a.py"
    source.write_text("x=1\n")
    link = tmp_path / "link.py"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="symlink"):
        analyze(link)


def test_source_fifo_is_refused_before_open(tmp_path: Path) -> None:
    import os

    from pp_pytrace.frontend.discovery import read_bounded

    if not hasattr(os, "mkfifo"):
        pytest.skip("named pipes are a POSIX source-ingestion regression")
    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular file"):
        discover(tmp_path)
    with pytest.raises(ParseFailure, match="regular file"):
        read_bounded(fifo)
