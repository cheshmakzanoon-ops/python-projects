"""Seeded workloads, independent dictionary checks, and equivalent SQLite timings."""

from __future__ import annotations

import hashlib
import random
import resource
import shutil
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Literal

from pp_strata import Database
from pp_strata.evidence import provenance


def key_for(index: int) -> bytes:
    return index.to_bytes(16)


def value_for(index: int) -> bytes:
    return hashlib.sha256(index.to_bytes(16)).digest() * 8


def distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "minimum_seconds": ordered[0],
        "maximum_seconds": ordered[-1],
    }


def metric_integer(metrics: dict[str, object], key: str) -> int:
    value = metrics[key]
    if not isinstance(value, int):
        raise TypeError(f"metric {key} is not an integer")
    return value


def commit_comparison(root: Path, count: int, repetitions: int = 5) -> dict[str, object]:
    result: dict[str, object] = {}
    for engine in ("strata", "sqlite"):
        for batch in (1, 100):
            measurements: list[float] = []
            for repeat in range(repetitions + 1):
                path = root / f"commit-{engine}-{batch}-{repeat}"
                if engine == "strata":
                    with Database.open(path) as db:
                        start = time.perf_counter()
                        for index in range(0, count, batch):
                            with db.begin() as tx:
                                for item in range(index, min(index + batch, count)):
                                    tx.put(key_for(item), value_for(item))
                        elapsed = time.perf_counter() - start
                        with db.snapshot() as snap:
                            assert len(list(snap.scan())) == count
                    shutil.rmtree(path)
                else:
                    connection = sqlite3.connect(path)
                    try:
                        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
                        connection.execute("PRAGMA synchronous=FULL")
                        assert connection.execute("PRAGMA synchronous").fetchone() == (2,)
                        connection.execute(
                            "CREATE TABLE records (key BLOB PRIMARY KEY, value BLOB NOT NULL)"
                        )
                        start = time.perf_counter()
                        for index in range(0, count, batch):
                            with connection:
                                connection.executemany(
                                    "INSERT INTO records VALUES (?, ?)",
                                    [
                                        (key_for(item), value_for(item))
                                        for item in range(index, min(index + batch, count))
                                    ],
                                )
                        elapsed = time.perf_counter() - start
                        assert connection.execute("SELECT COUNT(*) FROM records").fetchone() == (
                            count,
                        )
                    finally:
                        connection.close()
                    path.unlink()
                if repeat:
                    measurements.append(elapsed)
            summary = distribution(measurements)
            result[f"{engine}_batch_{batch}"] = {
                **summary,
                "records": count,
                "records_per_second": count / summary["median_seconds"],
                "raw_seconds": measurements,
            }
    return result


def benchmark(output: Path, profile: Literal["ci", "standard"], seed: int) -> dict[str, object]:
    before = provenance()
    count, mixed = (2000, 2000) if profile == "ci" else (250000, 200000)
    rng = random.Random(seed)
    oracle: dict[bytes, bytes] = {}
    read_times: list[float] = []
    write_times: list[float] = []
    compaction_stalls: list[float] = []
    db_path = output / "workload"
    start = time.perf_counter()
    with Database.open(db_path) as db:
        for batch in range(0, count, 100):
            tick = time.perf_counter()
            with db.begin() as tx:
                for i in range(batch, min(batch + 100, count)):
                    key, value = key_for(i), value_for(i)
                    tx.put(key, value)
                    oracle[key] = value
            write_times.append(time.perf_counter() - tick)
        initial_seconds = time.perf_counter() - start
        for step in range(mixed):
            index = rng.randrange(count)
            key = key_for(index)
            choice = rng.randrange(10)
            tick = time.perf_counter()
            if choice < 6:
                with db.snapshot() as snap:
                    assert snap.get(key) == oracle.get(key)
                read_times.append(time.perf_counter() - tick)
            else:
                with db.begin() as tx:
                    if choice == 6:
                        tx.delete(key)
                        oracle.pop(key, None)
                    else:
                        value = value_for(count + step)
                        tx.put(key, value)
                        oracle[key] = value
                write_times.append(time.perf_counter() - tick)
        with db.snapshot() as snap:
            assert list(snap.scan()) == sorted(oracle.items())
        tick = time.perf_counter()
        db.compact()
        compaction_stalls.append(time.perf_counter() - tick)
        metrics = db.inspect()
        with db.snapshot() as snap:
            assert list(snap.scan()) == sorted(oracle.items())
    tick = time.perf_counter()
    with Database.open(db_path) as db, db.snapshot() as snap:
        recovery_seconds = time.perf_counter() - tick
        assert list(snap.scan()) == sorted(oracle.items())
    # Independent churn phase: repeatedly overwrite/delete a bounded hot set.
    churn_count = 2000 if profile == "ci" else 50000
    tick = time.perf_counter()
    with Database.open(output / "churn") as db:
        for index in range(churn_count):
            key = key_for(index % 100)
            with db.begin() as tx:
                if index % 3:
                    tx.put(key, value_for(index))
                else:
                    tx.delete(key)
        before_churn_compact = db.inspect()["disk_bytes"]
        db.compact()
        after_churn_compact = db.inspect()["disk_bytes"]
    churn_seconds = time.perf_counter() - tick
    comparison = commit_comparison(output, 200 if profile == "ci" else 2000)
    after = provenance()
    if before["source_content_sha256"] != after["source_content_sha256"]:
        raise RuntimeError("source changed during benchmark")
    logical = metric_integer(metrics, "logical_bytes_written")
    physical = metric_integer(metrics, "wal_bytes_written") + metric_integer(
        metrics, "table_bytes_written"
    )
    live_bytes = sum(len(k) + len(v) for k, v in oracle.items())
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return {
        **before,
        "seed": seed,
        "dataset_id": f"strata-v1:{hashlib.sha256(f'{seed}:{count}:{mixed}'.encode()).hexdigest()}",
        "profile": profile,
        "parameters": {
            "initial_records": count,
            "mixed_operations": mixed,
            "churn_operations": churn_count,
            "key_bytes": 16,
            "value_bytes": 256,
            "durability": "WAL fsync per commit",
            "sqlite": "journal_mode=WAL; synchronous=FULL; one connection; same rows and transaction sizes",
            "cache_blocks_per_table": 32,
            "block_target_bytes": 65536,
            "memtable_bytes": 8388608,
            "processes": 1,
            "threads": 1,
            "cache_state": "warm in-process reads; reopen OS cache not dropped",
        },
        "warmup_runs": 1,
        "measurement_runs": 5,
        "metrics": {
            "initial_seconds": initial_seconds,
            "initial_records_per_second": count / initial_seconds,
            "read_latency": distribution(read_times),
            "write_or_batch_latency": distribution(write_times),
            "compaction_stall_seconds": compaction_stalls,
            "recovery_seconds": recovery_seconds,
            "peak_rss_bytes": peak,
            "disk_bytes": metrics["disk_bytes"],
            "write_amplification": physical / max(1, logical),
            "space_amplification": metric_integer(metrics, "disk_bytes") / max(1, live_bytes),
            "read_amplification_bytes_per_requested_value": metric_integer(
                metrics, "block_read_bytes"
            )
            / max(1, len(read_times) * 256),
            "io_counters": metrics,
            "durable_commit_comparison": comparison,
            "churn": {
                "seconds": churn_seconds,
                "disk_before_compaction": before_churn_compact,
                "disk_after_compaction": after_churn_compact,
            },
        },
        "correctness_checks": {
            "mixed_points_match_dictionary": True,
            "full_scan_before_after_compaction": True,
            "recovered_scan_matches_dictionary": True,
            "comparison_record_counts": True,
            "source_unchanged": True,
        },
        "status": "passed",
        "limitations": [
            "Synthetic local filesystem workload, no power-loss simulation",
            "Five repetitions apply to commit comparisons; mixed workload runs once",
            "Read amplification includes compaction and recovery reads; it is a conservative whole-workload ratio",
            "ru_maxrss includes Python and independent dictionary oracle; Linux KiB conversion",
            "OS page cache is not controlled; concurrent host work can affect timing",
        ],
    }
