"""Deterministic correctness exercise; not a capacity or latency benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sqlite3
import time
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any

from pp_quarry import Config, Conflict, Contract, Field, Lakehouse, Snapshot, recover
from pp_quarry.cli import owned_output
from pp_quarry.evidence import provenance
from pp_quarry.workloads import (
    actual,
    daily_actual,
    daily_digest,
    daily_oracle,
    oracle,
    row_digest,
    write_events,
)


def record(
    index: int, version: int, value: int, day: int, *, delete: bool = False
) -> dict[str, Any]:
    return {
        "source_namespace": f"fleet-{index % 2}",
        "key": str(index // 2),
        "version": version,
        "operation": "delete" if delete else "upsert",
        "payload": {}
        if delete
        else {
            "device": f"device-{index % 1000}",
            "day": f"2026-01-{day:02}",
            "value": value,
        },
    }


def pinned_digest(view: Snapshot) -> str:
    return row_digest(
        (row["namespace"], row["key"], row["version"], row["payload"]) for row in view.rows()
    )


def run(output: Path, rows: int, buckets: int, seed: int) -> dict[str, Any]:
    if rows < 100:
        raise ValueError("at least 100 original events are required")
    owned_output(output)
    (output / "inputs").mkdir()
    before = provenance(seed, "incremental-correctness")
    files: list[Path] = []
    phases = []
    old: Snapshot | None = None
    first = 0
    first_facts = first_daily = ""
    current_contract = Contract()
    started = time.perf_counter()
    with Lakehouse(output / "lake", Config(buckets=buckets, threads=1, memory_mb=128)) as lake:

        def phase(name: str, records: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
            if records is None:
                incoming = files[-1]
            else:
                incoming = output / "inputs" / f"{name}.ndjson"
                write_events(incoming, records)
                files.append(incoming)
            plan = lake.plan(incoming, current_contract)
            snapshot = lake.ingest(incoming, current_contract)
            reference = output / "inputs" / f"{name}-reference.sqlite"
            expected, _ = oracle(files, reference)
            expected_daily = daily_oracle(reference)
            assert actual(lake) == expected, f"facts mismatch after {name}"
            assert daily_actual(lake) == expected_daily, f"daily mismatch after {name}"
            with closing(sqlite3.connect(reference)) as db:
                identities = db.execute(
                    "SELECT count(*) FROM (SELECT namespace,key,version FROM arrivals GROUP BY namespace,key,version)"
                ).fetchone()[0]
            reference.unlink()
            assert lake.db.execute("SELECT count(*) FROM identities").fetchone()[0] == identities
            assert lake.db.execute("SELECT count(*) FROM sources").fetchone()[0] == len(files)
            if old is not None:
                assert pinned_digest(old) == first_facts
                assert daily_digest(old.rows("daily")) == first_daily
            manifest = lake.manifest(snapshot)
            result = {
                "phase": name,
                "snapshot": snapshot,
                "facts_sha256": expected,
                "daily_sha256": expected_daily,
                "historical_identities": identities,
                "live_rows": manifest["quality"]["live_rows"],
                "stats": manifest["stats"],
                "planned_buckets": [
                    key
                    for key, nodes in plan["partitions"].items()
                    if any(node["action"] == "build" for node in nodes.values())
                ],
            }
            phases.append(result)
            return result

        def original(index: int) -> dict[str, Any]:
            return record(index, 1, (index * 17 + seed) % 1000 - 500, index % 28 + 1)

        initial = phase("original", (original(index) for index in range(rows)))
        first = initial["snapshot"]
        old = Snapshot(lake.root, first)
        first_facts, first_daily = initial["facts_sha256"], initial["daily_sha256"]
        try:
            phase(
                "corrections",
                (
                    record(index, 3, (index * 7 + seed) % 777 - 300, (index + 7) % 28 + 1)
                    for index in range(rows // 5)
                ),
            )

            def obsolete() -> Iterable[dict[str, Any]]:
                for index in range(rows // 10):
                    yield record(index, 2, -999, 28)
                for index in range(20):
                    yield original(index)

            unchanged = phase("obsolete-and-replayed", obsolete())
            assert unchanged["stats"]["bytes_written"] == 0
            phase("deletes", (record(index, 4, 0, 1, delete=True) for index in range(0, rows, 11)))
            current_contract = Contract(
                {**current_contract.fields, "firmware": Field("string", True)}
            )

            def additions() -> Iterable[dict[str, Any]]:
                for index in range(100):
                    value = record(index, 5, 10, index % 28 + 1)
                    value["payload"]["firmware"] = "v5"
                    yield value

            phase("schema-addition", additions())
            targeted = phase("targeted-move", [record(0, 6, 37, 28)])
            key_bytes = json.dumps(["fleet-0", "0"], separators=(",", ":")).encode()
            expected_bucket = str(
                int.from_bytes(hashlib.sha256(key_bytes).digest()[:8], "big") % buckets
            )
            assert targeted["planned_buckets"] == [expected_bucket]
            current_contract = Contract(
                current_contract.fields, minimum=-1000, maximum=1000, min_rows=1, max_rows=rows
            )
            policy = phase("quality-policy", None)
            assert policy["stats"]["bytes_written"] == 0
            assert policy["stats"]["reused_nodes"] == buckets * 3
            recovery = recover(lake, retain=2)
            assert first in recovery["snapshots"]
            assert pinned_digest(old) == first_facts
        finally:
            old.close()
        recover(lake, retain=1)
        assert first not in lake.snapshots()
    with Lakehouse(output / "lake") as lake:
        historical = lake.lineage("fleet-0", "0", as_of_snapshot=first)
        assert [entry["version"] for entry in historical["versions"]] == [1]
        conflict = output / "inputs" / "historical-conflict.ndjson"
        write_events(conflict, [record(0, 1, 999, 1)])
        try:
            lake.ingest(conflict)
        except Conflict:
            pass
        else:
            raise AssertionError("historical conflict survived retention/restart undetected")
        assert actual(lake) == phases[-1]["facts_sha256"]
        assert daily_actual(lake) == phases[-1]["daily_sha256"]
        lake.validate()
    assert (
        before["source_content_sha256"]
        == provenance(seed, "incremental-correctness")["source_content_sha256"]
    )
    result = {
        **before,
        "status": "passed",
        "original_events": rows,
        "buckets": buckets,
        "duckdb_threads": 1,
        "duckdb_memory_mb": 128,
        "phases": phases,
        "elapsed_seconds": time.perf_counter() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "scope": "One deterministic correctness exercise on a shared Linux host; not a capacity measurement.",
    }
    (output / "report.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=50000)
    parser.add_argument("--buckets", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.rows, args.buckets, args.seed)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "original_events",
                    "buckets",
                    "elapsed_seconds",
                    "peak_rss_bytes",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
