"""Runnable demonstrations, replay, inspection, and reproducible benchmarks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import shutil
import statistics
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path

import typer

from pp_current import Config, Journal, Runtime
from pp_current.diagnostics.oracle import reconcile
from pp_current.diagnostics.workload import INPUTS, generate
from pp_current.sources.ndjson import read_ndjson

MARKER = ".current-owned-demo"
MARKER_TEXT = "Current generated demo state v1\n"


def safe_output(output: Path) -> Path:
    output = output.absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("refusing symlink output or ancestor")
    return output


def has_ownership(output: Path) -> bool:
    marker = output / MARKER
    return (
        not marker.is_symlink()
        and marker.is_file()
        and marker.stat().st_size == len(MARKER_TEXT.encode("utf-8"))
        and marker.read_text(encoding="utf-8") == MARKER_TEXT
    )


def owned(output: Path) -> None:
    output = safe_output(output)
    if output.exists() and any(output.iterdir()) and not has_ownership(output):
        raise ValueError("refusing nonempty output without Current ownership marker")
    output.mkdir(parents=True, exist_ok=True)
    if not has_ownership(output):
        with (output / MARKER).open("x", encoding="utf-8") as marker:
            marker.write(MARKER_TEXT)


def fresh_output(output: Path) -> None:
    owned(output)
    if any(path.name != MARKER for path in output.iterdir()):
        raise ValueError("run directory contains state; select fresh output or clean-demo")


def execute(
    output: Path,
    count: int,
    seed: int,
    *,
    hot: bool = False,
    oracle: bool = True,
    crash: bool = False,
) -> dict[str, object]:
    fresh_output(output)
    path = output / "current.sqlite"
    if path.exists():
        raise ValueError("run directory already contains state; select fresh output or clean-demo")
    journal = Journal(path, max_disk_bytes=4 * 1024**3, max_outbox=10_000_000)
    config = Config(INPUTS, state_limit=1_000_000)
    start = time.perf_counter()
    raw: list[dict[str, object]] = []
    batch = []
    for record in generate(count, seed, hot=hot):
        batch.append(record)
        if len(batch) == 1000:
            admitted = journal.admit(batch)
            if oracle:
                raw.extend(r.dictionary() for r in admitted)
            batch = []
    if batch:
        admitted = journal.admit(batch)
        if oracle:
            raw.extend(r.dictionary() for r in admitted)
    admission_seconds = time.perf_counter() - start
    crash_returncode: int | None = None
    if crash:
        journal.close()
        code = """
import asyncio, os, sys
from pathlib import Path
from enum import Enum
import typer
from pp_current import Config, Journal, Runtime
from pp_current.diagnostics.workload import INPUTS
j = Journal(Path(sys.argv[1]), failpoint=lambda p: os._exit(73) if p == 'checkpoint-before-publication' else None)
asyncio.run(Runtime(j, j.recover(Config(INPUTS)), capacity=128).run(checkpoint_interval=10000))
"""
        killed = subprocess.run(
            [sys.executable, "-c", code, str(path)], timeout=90, capture_output=True
        )
        crash_returncode = killed.returncode
        if killed.returncode != 73:
            raise RuntimeError(killed.stderr.decode())
        journal = Journal(path, max_disk_bytes=4 * 1024**3, max_outbox=10_000_000)
    runtime = Runtime(journal, journal.recover(config), capacity=128)
    start = time.perf_counter()
    asyncio.run(runtime.run(checkpoint_interval=10_000))
    elapsed = time.perf_counter() - start
    start = time.perf_counter()
    restored = journal.recover(config)
    restore = time.perf_counter() - start
    outputs = journal.export()
    expected_dispositions, expected = (
        reconcile(
            raw,
            inputs=INPUTS,
            size=config.size,
            slide=config.slide,
            lateness=config.lateness,
            interval=config.join_interval,
        )
        if oracle
        else ([], {})
    )
    actual = {
        str(r["operator_id"]) + ":" + str(r["logical_result_key"]): r["payload"] for r in outputs
    }
    correct = actual == expected if oracle else sum(restored.dispositions.values()) == count
    if oracle:
        oracle_counts = {name: expected_dispositions.count(name) for name in restored.dispositions}
        correct = correct and oracle_counts == restored.dispositions
    report: dict[str, object] = {
        "events": count,
        "records": restored.position,
        "dispositions": restored.dispositions,
        "outputs": len(outputs),
        "oracle_matches": correct,
        "processing_seconds": elapsed,
        "checkpoint_seconds": journal.checkpoint_seconds,
        "max_watermark_lag_ms": restored.max_watermark_lag,
        "max_finalization_lag_ms": restored.max_finalization_lag,
        "controlled_crash_exit": crash_returncode,
        "admission_seconds": admission_seconds,
        "throughput_events_s": count / elapsed,
        "restore_seconds": restore,
        "buffer_peak": runtime.metrics.queue_peak,
        "state_peak": restored.peak_state,
        "watermark": restored.progress.watermark,
        "disk_bytes": sum(p.stat().st_size for p in output.glob("*.sqlite*")),
    }
    (output / "timeline.json").write_text(
        json.dumps(
            {
                "scope": "last 40 processed records; full history remains in SQLite ingress",
                "columns": ["ingress_ordinal", "disposition", "watermark_ms"],
                "records": list(runtime.engine.trace)[-40:],
            },
            indent=2,
        )
        + "\n"
    )
    (output / "results.json").write_text(json.dumps(outputs, indent=2) + "\n")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    journal.close()
    if not correct:
        raise AssertionError("independent trace reconciliation failed")
    return report


def provenance(seed: int, profile: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    source = hashlib.sha256()
    for path in sorted(
        [
            *root.glob("src/**/*.py"),
            *root.glob("tests/**/*.py"),
            root / "pyproject.toml",
            root / "uv.lock",
            root / ".python-version",
        ]
    ):
        source.update(str(path.relative_to(root)).encode())
        source.update(path.read_bytes())
    repo = root.parents[1]
    contract = hashlib.sha256()
    for name in ("AGENTS.md", "ruff.toml", "portfolio.toml", "scripts/portfolio.py"):
        path = repo / name
        if path.exists():
            contract.update(name.encode())
            contract.update(path.read_bytes())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--", "."], cwd=root, text=True
        ).strip()
    )
    return {
        "schema_version": 1,
        "project": "current",
        "source_commit": commit,
        "source_dirty": dirty,
        "source_scope": "project",
        "source_content_sha256": source.hexdigest(),
        "root_contract_sha256": contract.hexdigest(),
        "lockfile_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "memory_limit_bytes": None,
        "seed": seed,
        "dataset_id": hashlib.sha256(
            (root / "src/pp_current/diagnostics/workload.py").read_bytes()
            + str(seed).encode()
            + profile.encode()
        ).hexdigest(),
        "profile": profile,
        "warmup_runs": 1,
        "measurement_runs": 5,
    }


app = typer.Typer(no_args_is_help=True, help=__doc__)


class Profile(str, Enum):
    ci = "ci"
    standard = "standard"


@app.command()
def demo(output: Path = typer.Option(...), seed: int = 1729) -> None:
    print(json.dumps(execute(output, 10_000, seed, crash=True), indent=2))


@app.command("clean-demo")
def clean_demo(output: Path = typer.Option(...)) -> None:
    output = safe_output(output)
    if not has_ownership(output):
        raise ValueError("refusing to remove unowned or symlink state")
    shutil.rmtree(output)


@app.command()
def inspect(output: Path = typer.Option(...)) -> None:
    journal = Journal(output / "current.sqlite", read_only=True)
    try:
        print(json.dumps(journal.export(), indent=2))
    finally:
        journal.close()


@app.command()
def replay(output: Path = typer.Option(...), input: Path = typer.Option(...)) -> None:
    fresh_output(output)
    journal = Journal(output / "current.sqlite")
    try:
        records = list(read_ndjson(input))
        if not records:
            raise ValueError("replay input contains no records")
        journal.admit(records)
        config = Config(tuple(sorted({record.input_id for record in records})))
        asyncio.run(Runtime(journal, journal.recover(config)).run())
        print(json.dumps(journal.export(), indent=2))
    finally:
        journal.close()


@app.command()
def benchmark(
    output: Path = typer.Option(...), profile: Profile = Profile.ci, seed: int = 1729
) -> None:
    identity_before = provenance(seed, profile.value)
    fresh_output(output)
    count = 10_000 if profile.value == "ci" else 1_000_000
    execute(output / "warmup", min(count, 10_000), seed)
    reports = []
    # Linux benchmark RSS includes Python and SQLite native allocations.
    repetitions = 5 if profile == Profile.ci else 1
    for run in range(repetitions):
        run_path = output / f"run-{run}"
        reports.append(execute(run_path, count, seed, oracle=True))
        if profile == Profile.standard:
            clean_demo(run_path)
            run_path.mkdir()
            (run_path / "report.json").write_text(json.dumps(reports[-1], indent=2) + "\n")
    hot = execute(output / "hot", count, seed, hot=True, oracle=True)
    if profile == Profile.standard:
        clean_demo(output / "hot")
        (output / "hot").mkdir()
        (output / "hot" / "report.json").write_text(json.dumps(hot, indent=2) + "\n")
    try:
        import resource

        memory: int | None = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        memory = None
    result = provenance(seed, profile.value)
    if result["source_content_sha256"] != identity_before["source_content_sha256"]:
        raise RuntimeError("source changed while benchmark ran; discard affected evidence")
    result.update(
        {
            "measurement_runs": repetitions,
            "repetition_reason": "Five CI repetitions; standard uses one full ordinary and one full hot million-event run because durable admission, output publication and full independent reconciliation are costly.",
            "parameters": {
                "events": count,
                "workers": 4,
                "threads": 1,
                "checkpoint_interval": 10_000,
                "window_ms": 30_000,
                "lateness_ms": 10_000,
                "durability": "SQLite WAL synchronous FULL",
            },
            "metrics": {
                "runs": reports,
                "hot": hot,
                "peak_process_rss_bytes": memory,
                "median_throughput": statistics.median(
                    float(str(r["throughput_events_s"])) for r in reports
                ),
            },
            "correctness_checks": {"reconciled": all(r["oracle_matches"] for r in reports)},
            "status": "passed",
        }
    )
    (output / "benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
