from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pp_pytrace.cache import analyze
from pp_pytrace.workloads import clean_demo, demo

PROJECT = Path(__file__).parents[2]


def test_py01_full_labeled_corpus() -> None:
    root = PROJECT / "tests/fixtures/labeled"
    labels = json.loads((root / "labels.json").read_text())
    result = analyze(root)
    expected = {
        (name, item["line"], item["rule_id"])
        for name, cases in labels["files"].items()
        for item in cases
    }
    actual = {
        (item.path, item.location.line, item.rule_id)
        for item in result.diagnostics
        if item.rule_id in ("PT001", "PT002", "PT003")
    }
    assert len(labels["files"]) >= 50
    assert labels["lines"] >= 5_000
    assert actual == expected
    assert not result.parse_failures


def test_public_cli_demo_and_analysis(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    command = [sys.executable, "-m", "pp_pytrace.cli"]
    result = subprocess.run(
        [*command, "demo", "--output", str(output), "--seed", "1729"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data["findings"]) == {"PT001", "PT002", "PT003"}
    assert data["idempotent"]
    report = output / "diagnostics.json"
    assert len(json.loads(report.read_text())["diagnostics"]) >= 3
    result = subprocess.run(
        [*command, "analyze", str(output / "trusted"), "--format", "sarif"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["version"] == "2.1.0"


def test_owned_cleanup_preserves_user_file(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    assert demo(output)["status"] == "passed"
    (output / "user-note.txt").write_text("keep")
    clean_demo(output)
    assert (output / "user-note.txt").read_text() == "keep"


def test_public_diff_apply_cache_and_explain(tmp_path: Path, capsys: object) -> None:
    from pp_pytrace.cli import main

    root = tmp_path / "source"
    root.mkdir()
    source = root / "service.py"
    before = 'import os\nx=str("hello")\nos.system(input())\n'
    source.write_text(before)
    plan = tmp_path / "plan.json"
    patch = tmp_path / "preview.patch"
    assert main(["diff", str(root), "service.py", "--plan", str(plan), "--output", str(patch)]) == 0
    assert '-x=str("hello")' in patch.read_text()
    assert (
        main(
            [
                "apply",
                str(plan),
                "--root",
                str(tmp_path),
                "--journal",
                str(tmp_path / "wrong-journal"),
            ]
        )
        == 2
    )
    assert source.read_text() == before
    assert (
        main(["apply", str(plan), "--root", str(root), "--journal", str(tmp_path / "journal")]) == 0
    )
    assert source.read_text() == before.replace('str("hello")', '"hello"')
    output = tmp_path / "report.json"
    cache = tmp_path / "cache.json"
    assert (
        main(
            [
                "analyze",
                str(root),
                "--format",
                "json",
                "--output",
                str(output),
                "--cache",
                str(cache),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert main(["explain", str(root), report["diagnostics"][0]["id"]]) == 0
    assert main(["cache", "inspect", str(cache)]) == 0
    plan.write_text('{"schema_version": 2}')
    assert (
        main(
            [
                "apply",
                str(plan),
                "--root",
                str(root),
                "--journal",
                str(tmp_path / "malformed-journal"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "malformed-journal").exists()
