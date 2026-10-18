"""Deterministic demonstrations and cold/cache/invalidation benchmark workloads."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from pp_pytrace.cache import analyze
from pp_pytrace.codemods.plan import apply, create_plan, patch
from pp_pytrace.evidence import metadata
from pp_pytrace.reporting.sarif import sarif, validate

OWNER = ".pp-pytrace-demo.json"
SERVICE = """import subprocess as sp
import time
from pp_pytrace.trusted_api import deliver

async def service(cursor):
    value = input("name")
    sp.run("echo " + value, shell=True)
    cursor.execute(f"SELECT * FROM users WHERE name = '{value}'")
    time.sleep(1)
    result = str("ready")  # preserve this comment
    return deliver(result, timeout=3)
"""


def owned_output(output: Path, seed: int) -> Path:
    if not output.is_absolute():
        raise ValueError("output must be an absolute path")
    if output.is_symlink():
        raise ValueError("output symlink refused")
    output.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in output.rglob("*")):
        raise ValueError("owned output contains symlink")
    marker = output / OWNER
    if not marker.exists() and any(output.iterdir()):
        raise ValueError("refusing to adopt nonempty output directory")
    if marker.exists():
        data = json.loads(marker.read_text())
        if data.get("owner") != "pp-pytrace" or data.get("root") != str(output.resolve()):
            raise ValueError("output ownership marker mismatch")
    marker.write_text(
        json.dumps(
            {
                "owner": "pp-pytrace",
                "schema_version": 1,
                "seed": seed,
                "root": str(output.resolve()),
            }
        )
        + "\n"
    )
    return output


def clean_demo(output: Path) -> None:
    if not output.is_absolute() or output.is_symlink() or not (output / OWNER).is_file():
        raise ValueError("refusing to clean unowned path")
    data = json.loads((output / OWNER).read_text())
    if data.get("owner") != "pp-pytrace" or data.get("root") != str(output.resolve()):
        raise ValueError("output ownership marker mismatch")
    # Only fixed generated paths are removed, preserving anything a user added.
    for name in (
        "trusted",
        "journal",
        "corpus",
        "cache",
        "benchmark.json",
        "demo.json",
        "diagnostics.json",
        "diagnostics.sarif",
        "preview.patch",
        "plan.json",
    ):
        path = output / name
        if path.is_symlink():
            raise ValueError("refusing cleanup through symlink")
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    (output / OWNER).unlink()
    if not any(output.iterdir()):
        output.rmdir()


def demo(output: Path, seed: int = 1729) -> dict[str, Any]:
    output = owned_output(output, seed)
    trusted = output / "trusted"
    trusted.mkdir(exist_ok=True)
    path = trusted / "service.py"
    path.write_text(SERVICE)
    before = analyze(trusted)
    diagnostics = before.to_dict()
    (output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    document = sarif(before.diagnostics)
    validate(document)
    (output / "diagnostics.sarif").write_text(json.dumps(document, indent=2) + "\n")
    plan = create_plan(trusted, ["service.py"])
    (output / "preview.patch").write_text(patch(plan))
    (output / "plan.json").write_text(json.dumps(plan.to_dict(), indent=2) + "\n")
    journal = output / "journal"
    if journal.exists():
        shutil.rmtree(journal)
    apply(plan, journal)
    after = analyze(trusted)
    second = create_plan(trusted, ["service.py"])
    security_before = [
        item.rule_id for item in before.diagnostics if item.rule_id in ("PT001", "PT002", "PT003")
    ]
    security_after = [
        item.rule_id for item in after.diagnostics if item.rule_id in ("PT001", "PT002", "PT003")
    ]
    report = {
        "schema_version": 1,
        "project": "pytrace",
        "seed": seed,
        "findings": security_before,
        "safe_edits": len(plan.edits),
        "transformations": 2,
        "patch": "preview.patch",
        "idempotent": not second.edits,
        "security_findings_preserved": security_before == security_after,
        "status": "passed"
        if set(security_before) == {"PT001", "PT002", "PT003"}
        and not second.edits
        and security_before == security_after
        else "failed",
    }
    (output / "demo.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _corpus(output: Path, count: int, chunk_size: int = 1) -> tuple[Path, dict[str, Any]]:
    source = Path(__file__).resolve().parents[2] / "tests/fixtures/labeled"
    if not source.is_dir():
        source = Path(__file__).with_name("data") / "labeled"
    if not source.is_dir():
        raise ValueError("bundled benchmark corpus missing")
    target = output / "corpus"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    originals = sorted(source.glob("*.py"))
    labels = json.loads((source / "labels.json").read_text())
    for index in range(0, count, chunk_size):
        text = "".join(
            originals[(index + offset) % len(originals)].read_text() for offset in range(chunk_size)
        )
        (target / f"service_{index // chunk_size:04d}.py").write_text(text)
    # Explicit local graph establishes dependency-aware invalidation independently.
    for index in range(10):
        import_line = "" if index == 0 else f"from graph_{index - 1:02d} import value\n"
        (target / f"graph_{index:02d}.py").write_text(import_line + f"value = {index}\n")
    return target, labels


def benchmark(output: Path, profile: str = "ci", seed: int = 1729) -> dict[str, Any]:
    output = owned_output(output, seed)
    record = metadata(seed, profile)
    count = 50 if profile == "ci" else 2240  # 250,880 labeled-template lines, plus dependency graph
    chunk_size = 1 if profile == "ci" else 10
    corpus, labels = _corpus(output, count, chunk_size)
    total_files = count // chunk_size + 10
    dataset_hash = hashlib.sha256()
    for path in sorted(corpus.glob("*.py")):
        dataset_hash.update(path.name.encode() + path.read_bytes())
    record["dataset_id"] = "pytrace-reviewed-v1:" + dataset_hash.hexdigest()
    record["parameters"].update(
        {
            "files": total_files,
            "fixture_files": count,
            "lines": sum(len(path.read_text().splitlines()) for path in corpus.glob("*.py")),
            "corpus": "original synthetic source, contextual variants; no independent real-world accuracy claim",
            "standard_cold_runs": 1 if profile == "standard" else 5,
        }
    )
    cache = output / "cache" / "analysis.json"
    warmup = analyze(corpus, cache)
    cold_times = []
    warm_times = []
    tracemalloc.start()
    for _ in range(1 if profile == "standard" else 5):
        start = time.perf_counter()
        cold = analyze(corpus)
        cold_times.append(time.perf_counter() - start)
        if [item.to_dict() for item in cold.diagnostics] != [
            item.to_dict() for item in warmup.diagnostics
        ]:
            raise AssertionError("cold/cache findings diverged")
    for _ in range(5):
        start = time.perf_counter()
        warm = analyze(corpus, cache)
        warm_times.append(time.perf_counter() - start)
        if warm.invalidated:
            raise AssertionError("unchanged files invalidated")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    changed = corpus / "graph_00.py"
    changed.write_text(changed.read_text() + "# changed dependency\n")
    start = time.perf_counter()
    incremental = analyze(corpus, cache)
    incremental_seconds = time.perf_counter() - start
    clean = analyze(corpus)
    equal = [item.to_dict() for item in incremental.diagnostics] == [
        item.to_dict() for item in clean.diagnostics
    ]
    expected = {
        (
            f"service_{index // chunk_size:04d}.py",
            item["line"] + (index % chunk_size) * 112,
            item["rule_id"],
        )
        for index in range(count)
        for item in labels["files"][f"service_{index % 50:02d}.py"]
    }
    actual = {
        (item.path, item.location.line, item.rule_id)
        for item in warmup.diagnostics
        if item.rule_id in ("PT001", "PT002", "PT003")
    }
    tp = len(expected & actual)
    record["metrics"] = {
        "cold_seconds": cold_times,
        "warm_seconds": warm_times,
        "warm_median_seconds": statistics.median(warm_times),
        "cold_median_seconds": statistics.median(cold_times),
        "incremental_seconds": incremental_seconds,
        "files_invalidated": len(incremental.invalidated),
        "parse_failures": warmup.parse_failures,
        "peak_python_tracemalloc_bytes": peak,
        "precision": (tp / len(actual) if actual else 1) if profile == "ci" else None,
        "recall": tp / len(expected) if profile == "ci" else None,
        "labeled_cases": len(expected) if profile == "ci" else 0,
        "files_per_second_cold": total_files / statistics.median(cold_times),
    }
    try:
        import resource

        unit = 1 if platform.system() == "Darwin" else 1024
        record["metrics"]["peak_analyzer_rss_bytes"] = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit
        )
        record["metrics"]["max_parser_child_peak_rss_bytes"] = (
            resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * unit
        )
    except ImportError:
        record["metrics"]["peak_analyzer_rss_bytes"] = None
        record["metrics"]["max_parser_child_peak_rss_bytes"] = None
        record["memory_limitation"] = "resource RSS accounting unavailable on this platform"
    record["correctness_checks"] = {
        "labels_exact": actual == expected,
        "incremental_equals_clean": equal,
        "dependency_closure_invalidated": set(incremental.invalidated)
        == {f"graph_{index:02d}.py" for index in range(10)},
        "no_parse_failures": warmup.parse_failures == 0,
    }
    record["status"] = "passed" if all(record["correctness_checks"].values()) else "failed"
    if profile == "standard":
        record["timing_limitation"] = (
            "One cold run to bound subprocess cost; five measured warm runs. Cold versus warm is descriptive, not a five-run statistical comparison. Labeled contextual variants are correlated."
        )
    record["source_digest_unchanged"] = (
        metadata(seed, profile)["source_content_sha256"] == record["source_content_sha256"]
    )
    (output / "benchmark.json").write_text(json.dumps(record, indent=2) + "\n")
    return record
