"""Required 100-seed × 5,000-operation persistence/reference suite.

Run with the installed package: uv run --locked python benchmarks/extended_stateful.py
--output /absolute/result.json. This is additional to the default Hypothesis suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import random
import tempfile
import time
from pathlib import Path

from pp_strata import Conflict, Database
from pp_strata.evidence import provenance


def run(seed: int, count: int, root: Path) -> dict[str, object]:
    rng = random.Random(seed)
    oracle: dict[bytes, bytes] = {}
    snapshots: dict[int, dict[bytes, bytes]] = {}
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        path = Path(temporary) / "db"
        db = Database.open(path, memtable_bytes=32768)
        held = db.snapshot()
        snapshots[held.sequence] = dict(oracle)
        try:
            for index in range(count):
                key = rng.randrange(600).to_bytes(2)
                operation = rng.randrange(10)
                if operation < 5:
                    with db.begin() as tx:
                        if operation == 0:
                            tx.delete(key)
                            oracle.pop(key, None)
                        else:
                            value = rng.randbytes(rng.randrange(120))
                            tx.put(key, value)
                            oracle[key] = value
                elif operation == 5:
                    with db.snapshot() as snap:
                        assert snap.get(key) == oracle.get(key)
                elif operation == 6:
                    upper = rng.randrange(600).to_bytes(2)
                    with db.snapshot() as snap:
                        assert list(snap.scan(key, upper)) == [
                            (k, v) for k, v in sorted(oracle.items()) if key <= k < upper
                        ]
                elif operation == 7:
                    tx = db.begin()
                    tx.put(key, b"aborted-private")
                    tx.abort()
                elif operation == 8:
                    # Conflicting writer and repeatable old read.
                    stale = db.begin()
                    previous = oracle.get(key)
                    with db.begin() as tx:
                        tx.put(key, b"winner")
                    oracle[key] = b"winner"
                    assert stale.get(key) == previous
                    stale.put(key, b"loser")
                    try:
                        stale.commit()
                    except Conflict:
                        pass
                    else:
                        raise AssertionError("conflicting commit succeeded")
                else:
                    assert list(held.scan()) == sorted(snapshots[held.sequence].items())
                if index % 200 == 0:
                    db.flush()
                if index % 1000 == 0:
                    db.compact()
                if index % 250 == 0:
                    assert list(held.scan()) == sorted(snapshots[held.sequence].items())
                    held.close()
                    held = db.snapshot()
                    snapshots = {held.sequence: dict(oracle)}
                if index and index % 1250 == 0:
                    held.close()
                    db.close()
                    db = Database.open(path, memtable_bytes=32768)
                    held = db.snapshot()
                    snapshots = {held.sequence: dict(oracle)}
                    assert list(held.scan()) == sorted(oracle.items())
            assert list(held.scan()) == sorted(snapshots[held.sequence].items())
            held.close()
            db.compact()
            with db.snapshot() as snap:
                assert list(snap.scan()) == sorted(oracle.items())
            sequence = db.sequence
            db.close()
            db = Database.open(path)
            with db.snapshot() as snap:
                assert list(snap.scan()) == sorted(oracle.items())
            assert db.sequence == sequence
        finally:
            held.close()
            db.close()
    digest = hashlib.sha256()
    for key, value in sorted(oracle.items()):
        digest.update(key + len(value).to_bytes(4) + value)
    return {
        "seed": seed,
        "operations": count,
        "final_sequence": sequence,
        "final_records": len(oracle),
        "oracle_sha256": digest.hexdigest(),
        "seconds": time.perf_counter() - start,
    }


def run_arguments(arguments: tuple[int, int, Path]) -> dict[str, object]:
    return run(*arguments)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--operations", type=int, default=5000)
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.output.is_absolute() or args.seeds <= 0 or args.operations <= 0:
        parser.error("output must be absolute; seed and operation counts must be positive")
    if args.output.exists() and not args.resume:
        parser.error("output already exists; choose a new file or explicitly --resume")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    before = provenance()
    results: list[dict[str, object]] = []
    completed: set[int] = set()
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text())
        if (
            previous.get("source_content_sha256") != before["source_content_sha256"]
            or previous.get("python") != before["python"]
            or previous.get("seeds") != args.seeds
            or previous.get("operations_per_seed") != args.operations
        ):
            raise ValueError("resume source/interpreter/workload does not match checkpoint")
        for result in previous.get("results", []):
            seed = result.get("seed")
            if (
                type(seed) is not int
                or not 0 <= seed < args.seeds
                or seed in completed
                or result.get("operations") != args.operations
            ):
                raise ValueError("invalid completed-seed checkpoint")
            completed.add(seed)
            results.append(result)

    def result_seed(result: dict[str, object]) -> int:
        seed = result["seed"]
        assert isinstance(seed, int)
        return seed

    def save(status: str) -> None:
        # Deterministic seed order regardless of process completion order.
        report = {
            **before,
            "suite": "extended-stateful",
            "seeds": args.seeds,
            "operations_per_seed": args.operations,
            "total_operations": args.seeds * args.operations,
            "completed_operations": len(results) * args.operations,
            "jobs": args.jobs,
            "status": status,
            "results": sorted(results, key=result_seed),
            "correctness_checks": [
                "independent dictionary and snapshot copies",
                "range scans",
                "abort isolation",
                "conflicting writers",
                "flush/compact with old snapshots",
                "periodic close/reopen",
                "final compaction/recovery",
            ],
        }
        temporary = args.output.with_suffix(args.output.suffix + ".pending")
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        temporary.replace(args.output)

    pending = [seed for seed in range(args.seeds) if seed not in completed]
    save("running")
    if args.jobs == 1:
        for seed in pending:
            results.append(run(seed, args.operations, args.output.parent))
            save("running")
            print(f"seed {seed + 1}/{args.seeds}: passed ({len(results)} completed)", flush=True)
    else:
        # Each process owns only its own temporary database. No shared engine
        # handle, snapshot, SQLite connection, or mutable oracle crosses processes.
        # Pool's context terminates workers on failure/cancellation, including
        # queued seeds. Spawn avoids inheriting any accidental process state.
        with multiprocessing.get_context("spawn").Pool(processes=args.jobs) as pool:
            arguments = ((seed, args.operations, args.output.parent) for seed in pending)
            for result in pool.imap_unordered(run_arguments, arguments, chunksize=1):
                seed = result_seed(result)
                results.append(result)
                save("running")
                print(
                    f"seed {seed + 1}/{args.seeds}: passed ({len(results)} completed)", flush=True
                )
    after = provenance()
    assert before["source_content_sha256"] == after["source_content_sha256"], "source changed"
    assert len(results) == args.seeds
    save("passed")


if __name__ == "__main__":
    main()
