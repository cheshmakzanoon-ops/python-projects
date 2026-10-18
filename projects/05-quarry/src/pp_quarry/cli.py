"""CLI for actual publication, pinned queries, plans, recovery and reproducible runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import shutil
import statistics
import time
from pathlib import Path
from typing import Any

from pp_quarry import Config, Contract, InjectedCrash, Lakehouse, Snapshot, recover
from pp_quarry.evidence import provenance
from pp_quarry.sources import file_hash
from pp_quarry.workloads import actual, evolved_contract, generate, make_event, oracle, write_events


def owned_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".quarry-demo"
    if any(path.iterdir()) and not marker.exists():
        raise ValueError("output must be empty or contain .quarry-demo ownership marker")
    if marker.exists():
        raise ValueError(
            "output already contains a run; clean-demo first or choose a fresh directory"
        )
    marker.write_text("Quarry generated demonstration state v1\n")


def clean_output(path: Path) -> None:
    if path.is_symlink() or not (path / ".quarry-demo").is_file():
        raise ValueError("refusing cleanup without Quarry demo ownership marker")
    allowed = {
        ".quarry-demo",
        "inputs",
        "lake",
        "report.json",
        "benchmark.json",
        "warmup",
        "run-0",
        "run-1",
        "run-2",
        "run-3",
        "run-4",
        "oracle.sqlite",
    }
    if any(child.name not in allowed or child.is_symlink() for child in path.iterdir()):
        raise ValueError("unexpected output contents; refusing cleanup")
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    path.rmdir()


def demo(output: Path, seed: int) -> dict[str, Any]:
    owned_output(output)
    before = provenance(seed, "demo")
    files = generate(output / "inputs", 200, seed)
    with Lakehouse(output / "lake") as lake:
        first = lake.ingest(files[0])
        with Snapshot(lake.root, first) as old:
            old_digest = actual(lake)
            targeted = output / "inputs" / "one-bucket.ndjson"
            write_events(targeted, [make_event(101, 2, 999, day=12)])
            plan = lake.plan(targeted)
            lake.ingest(targeted)
            one_bucket_stats = lake.manifest()["stats"]
            invalid = output / "inputs" / "invalid.ndjson"
            write_events(invalid, [make_event(102, 2, -1)])
            try:
                lake.ingest(invalid, Contract(minimum=0))
            except ValueError as exc:
                validation_error = str(exc)
            else:
                raise AssertionError("invalid batch accepted")
            try:
                lake.ingest(files[1], fault="after_files")
            except InjectedCrash:
                pass
            start = time.perf_counter()
            recovery = recover(lake)
            recovery_seconds = time.perf_counter() - start
            lake.ingest(files[1])
            lake.ingest(files[2])
            lake.ingest(files[3], evolved_contract())
            expected, full_seconds = oracle(
                [files[0], targeted, *files[1:]], output / "oracle.sqlite"
            )
            current_digest = actual(lake)
            assert current_digest == expected
            pinned_rows = list(old.rows(limit=3))
            assert pinned_rows[0]["version"] == 1
            report = {
                **before,
                "status": "passed",
                "initial_snapshot": first,
                "latest_snapshot": lake.manifest()["snapshot"],
                "one_bucket_plan": plan,
                "one_bucket_stats": one_bucket_stats,
                "validation_failure": validation_error,
                "recovery": recovery,
                "recovery_seconds": recovery_seconds,
                "full_rebuild_seconds": full_seconds,
                "old_snapshot_sample": pinned_rows,
                "old_digest": old_digest,
                "current_digest": current_digest,
                "correctness_checks": {
                    "independent_rebuild": current_digest == expected,
                    "one_bucket_only": one_bucket_stats["rewritten_buckets"] == 1,
                    "old_snapshot_unchanged": pinned_rows[0]["version"] == 1,
                },
                "lineage": lake.lineage("synthetic", "101"),
                "quality": lake.validate(),
                "metrics": lake.manifest()["stats"],
            }
    assert before["source_content_sha256"] == provenance(seed, "demo")["source_content_sha256"]
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def benchmark(output: Path, seed: int, profile: str) -> dict[str, Any]:
    owned_output(output)
    before = provenance(seed, profile)
    count, buckets = (20000, 8) if profile == "ci" else (5000000, 128)
    files = generate(output / "inputs", count, seed)
    expected, oracle_seconds = oracle(files, output / "oracle.sqlite")
    config = Config(buckets=buckets)
    warmup_count, warmup_buckets = 20000, 8
    if profile == "standard":
        warmup_files = generate(output / "inputs" / "warmup", warmup_count, seed)
        warmup_expected, _ = oracle(warmup_files, output / "inputs" / "warmup" / "oracle.sqlite")
    else:
        warmup_files, warmup_expected = files, expected
    samples: list[dict[str, Any]] = []
    measurements = 5 if profile == "ci" else 1
    for run in range(-1, measurements):
        active_files = warmup_files if run < 0 else files
        active_expected = warmup_expected if run < 0 else expected
        active_count = warmup_count if run < 0 else count
        active_config = Config(buckets=warmup_buckets) if run < 0 else config
        with Lakehouse(output / ("warmup" if run < 0 else f"run-{run}"), active_config) as lake:
            start = time.perf_counter()
            lake.ingest(active_files[0])
            original_seconds = time.perf_counter() - start
            start = time.perf_counter()
            for file in active_files[1:-1]:
                lake.ingest(file)
            lake.ingest(active_files[-1], evolved_contract())
            incremental_seconds = time.perf_counter() - start
            start = time.perf_counter()
            observed = actual(lake)
            query_seconds = time.perf_counter() - start
            if observed != active_expected:
                raise AssertionError("independent complete-rebuild mismatch")
            start = time.perf_counter()
            recovery = recover(lake)
            recovery_seconds = time.perf_counter() - start
            stats = lake.manifest()["stats"]
            bytes_written = sum(
                lake.manifest(s)["stats"]["bytes_written"] for s in lake.snapshots()
            )
            start = time.perf_counter()
            lake.build(force=True)
            full_rebuild_seconds = time.perf_counter() - start
            if actual(lake) != active_expected:
                raise AssertionError("forced full Parquet rebuild mismatch")
            sample = {
                "original_seconds": original_seconds,
                "incremental_seconds": incremental_seconds,
                "rows_per_second": active_count / original_seconds,
                "query_seconds": query_seconds,
                "recovery_seconds": recovery_seconds,
                "bytes_written": bytes_written,
                "parquet_transform_bytes_read": sum(
                    lake.manifest(s)["stats"]["parquet_input_bytes"] for s in lake.snapshots()
                ),
                "full_rebuild_seconds": full_rebuild_seconds,
                "rewritten_buckets": stats["rewritten_buckets"],
                "reused_nodes": stats["reused_nodes"],
                "incremental_full_ratio": incremental_seconds / full_rebuild_seconds,
                "full_oracle_ratio": incremental_seconds / oracle_seconds,
                "orphan_count": len(recovery["removed_orphans"]),
                "registry_identities": lake.db.execute(
                    "SELECT count(*) FROM identities"
                ).fetchone()[0],
                "publication_summaries": [
                    {
                        "snapshot": snapshot,
                        "manifest_sha256": hashlib.sha256(
                            json.dumps(
                                lake.manifest(snapshot), sort_keys=True, separators=(",", ":")
                            ).encode()
                        ).hexdigest(),
                        "files": sum(
                            len(nodes) for nodes in lake.manifest(snapshot)["partitions"].values()
                        ),
                        "live_rows": lake.manifest(snapshot)["quality"]["live_rows"],
                        "stats": lake.manifest(snapshot)["stats"],
                    }
                    for snapshot in lake.snapshots()
                ],
            }
            if run >= 0:
                samples.append(sample)
    report = {
        **before,
        "dataset_id": "synthetic-device-v1:" + file_hash(files[0]),
        "parameters": {
            "original_events": count,
            "corrections": count // 10,
            "deletes": count // 50,
            "schema_additions": min(100, count),
            "buckets": buckets,
            "batch_rows": config.batch_size,
            "max_record_bytes": config.max_record_bytes,
            "duckdb_memory_mb": config.memory_mb,
            "duckdb_threads": config.threads,
            "cache_state": "source read cache primed by independent oracle; engine warmed with 20,000 events; fresh catalogs per run",
        },
        "source_identities": [
            {"file": file.name, "sha256": file_hash(file), "bytes": file.stat().st_size}
            for file in files
        ],
        "warmup_parameters": {
            "original_events": warmup_count,
            "corrections": warmup_count // 10,
            "deletes": warmup_count // 50,
            "schema_additions": 100,
            "buckets": warmup_buckets,
            "fresh_catalog": True,
        },
        "warmup_runs": 1,
        "measurement_runs": measurements,
        "repetition_note": "CI has five measurements; standard has one measured run with 5,000,000 originals plus a bounded warmup with 20,000 originals to avoid duplicating the full historical catalog; the costly-run exception explicitly applies",
        "metrics": {
            "samples": samples,
            "rows_per_second_median": statistics.median(
                sample["rows_per_second"] for sample in samples
            ),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "source_bytes_read_per_run": sum(path.stat().st_size for path in files) * 4,
            "oracle_seconds": oracle_seconds,
        },
        "correctness_checks": {"independent_full_rebuild": True, "latest_digest": expected},
        "status": "passed",
    }
    assert before["source_content_sha256"] == provenance(seed, profile)["source_content_sha256"]
    (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("demo", "benchmark", "clean-demo"):
        child = sub.add_parser(command)
        child.add_argument("--output", type=Path, required=True)
        if command != "clean-demo":
            child.add_argument("--seed", type=int, default=1729)
        if command == "benchmark":
            child.add_argument("--profile", choices=("ci", "standard"), default="ci")
    for command in (
        "ingest",
        "plan",
        "build",
        "validate",
        "query",
        "snapshots",
        "lineage",
        "recover",
        "explain",
        "gc",
    ):
        child = sub.add_parser(command)
        child.add_argument("--dataset", type=Path, required=True)
        if command in {"ingest", "plan"}:
            child.add_argument("--source", type=Path, required=True)
            child.add_argument("--contract", type=Path)
        if command in {"query", "validate"}:
            child.add_argument("--snapshot", type=int)
        if command == "build":
            child.add_argument("--force", action="store_true")
        if command == "query":
            child.add_argument("--node", choices=("normalized", "facts", "daily"), default="facts")
            child.add_argument("--limit", type=int, default=100)
        if command == "lineage":
            child.add_argument("--namespace", required=True)
            child.add_argument("--key", required=True)
        if command == "gc":
            child.add_argument("--retain", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "clean-demo":
            clean_output(args.output.absolute())
            result: Any = {"cleaned": str(args.output)}
        elif args.command == "demo":
            result = demo(args.output.resolve(), args.seed)
        elif args.command == "benchmark":
            result = benchmark(args.output.resolve(), args.seed, args.profile)
        else:
            with Lakehouse(args.dataset) as lake:
                contract = (
                    Contract.from_dict(json.loads(args.contract.read_text()))
                    if getattr(args, "contract", None)
                    else None
                )
                if args.command == "ingest":
                    result = {"snapshot": lake.ingest(args.source, contract)}
                elif args.command == "plan":
                    result = lake.plan(args.source, contract)
                elif args.command == "build":
                    result = {"snapshot": lake.build(force=args.force)}
                elif args.command == "query":
                    with Snapshot(lake.root, args.snapshot) as handle:
                        result = list(handle.rows(args.node, args.limit))
                elif args.command == "validate":
                    result = lake.validate(args.snapshot)
                elif args.command == "snapshots":
                    result = lake.snapshots()
                elif args.command == "lineage":
                    result = lake.lineage(args.namespace, args.key)
                elif args.command == "recover":
                    result = recover(lake)
                elif args.command == "gc":
                    result = recover(lake, retain=args.retain)
                else:
                    result = lake.manifest()
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"quarry: {exc}\n")


if __name__ == "__main__":
    main()
