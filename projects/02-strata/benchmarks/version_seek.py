"""Small reproducible hot-version read workload; wall times are descriptive only."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import statistics
import tempfile
import time
from pathlib import Path

from pp_strata.codec.records import Record
from pp_strata.evidence import provenance
from pp_strata.memtable import Memtable
from pp_strata.sstable import Table, create_table

BASELINE_REVISION = "39d3a8d4be3e8e2e7de85379790d68f5367d6825"


def measure(versions: int, memory_queries: int, table_queries: int) -> dict[str, int | float]:
    records = [
        Record(b"hot", sequence, sequence.to_bytes(8) + bytes(120))
        for sequence in range(versions, 0, -1)
    ]
    memtable = Memtable()
    for record in records:
        memtable.add(record)
    started = time.perf_counter()
    for _ in range(memory_queries):
        if memtable.get(b"hot", 1) != records[-1]:
            raise AssertionError("memtable selected the wrong historical version")
    memory_seconds = time.perf_counter() - started
    with tempfile.TemporaryDirectory(prefix="strata-version-seek-") as temporary:
        path = Path(temporary) / "versions.sst"
        create_table(path, records)
        table = Table(path, cache_blocks=32)
        try:
            started = time.perf_counter()
            for _ in range(table_queries):
                if table.get(b"hot", 1) != records[-1]:
                    raise AssertionError("SSTable selected the wrong historical version")
            return {
                "memtable_seconds": memory_seconds,
                "table_seconds": time.perf_counter() - started,
                "table_blocks": len(table.blocks),
                "block_reads": table.block_reads,
                "block_read_bytes": table.read_bytes,
                "cache_hits": table.cache_hits,
                "cold_lookup_block_bound": math.ceil(math.log2(max(1, len(table.blocks)))) + 2,
            }
        finally:
            table.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--source-label", required=True, help="Caller label; not an observed revision"
    )
    parser.add_argument("--versions", type=int, default=20000)
    parser.add_argument("--memory-queries", type=int, default=100)
    parser.add_argument("--table-queries", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if min(args.versions, args.memory_queries, args.table_queries, args.repetitions) < 1:
        parser.error("workload counts must be positive")
    if not args.output.is_absolute() or args.output.exists():
        parser.error("output must be a new absolute path")
    algorithm_files = {
        "memtable": Path(inspect.getfile(Memtable)),
        "sstable": Path(inspect.getfile(Table)),
    }
    hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in algorithm_files.items()
    }
    before = provenance()
    results = [
        measure(args.versions, args.memory_queries, args.table_queries)
        for _ in range(args.repetitions)
    ]
    # The entire search path fits the declared 32-block cache for this fixture.
    # Cold and repeated I/O are recorded; no elapsed-time threshold is a gate.
    bounded = all(
        result["cold_lookup_block_bound"] <= 32
        and result["block_reads"] <= result["cold_lookup_block_bound"]
        for result in results
    )
    unchanged = hashes == {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in algorithm_files.items()
    }
    report = {
        **before,
        "suite": "hot-version-seek",
        "source_label": args.source_label,
        "comparison_baseline_revision": BASELINE_REVISION,
        "algorithm_file_sha256": hashes,
        "workload_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parameters": {
            "versions": args.versions,
            "value_bytes": 128,
            "key_hex": b"hot".hex(),
            "snapshot_sequence": 1,
            "memory_queries": args.memory_queries,
            "table_queries": args.table_queries,
            "cache_blocks": 32,
            "repetitions": args.repetitions,
            "setup_timing": "excluded: fresh skip-list construction and SSTable file write per repetition",
            "warmup": "none; each repetition begins with an empty application block cache",
        },
        "results": results,
        "median_memtable_seconds": statistics.median(
            float(result["memtable_seconds"]) for result in results
        ),
        "median_table_seconds": statistics.median(
            float(result["table_seconds"]) for result in results
        ),
        "checks": {"logarithmic_block_work": bounded, "algorithm_files_unchanged": unchanged},
        "status": "passed" if bounded and unchanged else "failed",
        "limits": "One deterministic hot key on a local filesystem; no whole-workload, cold-device, or production-capacity claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "report": str(args.output)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
