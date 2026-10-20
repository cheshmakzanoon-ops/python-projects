"""Compare sparse joins after a hot same-stream history, optionally with a Git revision.

Each version runs in its own process using the same installed interpreter. The
historical source tree is exported from Git objects without changing the checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pp_current.cli import provenance

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parents[1]
PREFIX = "projects/03-current/src/"
PROBE = """
import json, resource, statistics, sys, time
sys.path.insert(0, sys.argv[1])
from pp_current import Config, Engine, Record, canonical
count, repetitions = int(sys.argv[2]), int(sys.argv[3])
records = [Record('s', 0, n, n, 'hot', 1, ingress_ordinal=n+1) for n in range(count)]
records.extend([
    Record('s', 0, count, count//2, 'hot', stream='metadata', ingress_ordinal=count+1),
    Record('s', 0, count+1, kind='end', ingress_ordinal=count+2),
])
config = Config((canonical(['s', 0]),), size=count*2, slide=count*2,
                lateness=3, join_interval=2, state_limit=count+10)
timings, checks = [], []
for _ in range(repetitions):
    engine = Engine(config)
    started = time.perf_counter()
    for record in records:
        engine.apply(record)
    timings.append(time.perf_counter()-started)
    pairs = [json.loads(d.payload)['reading_ordinal'] for d in engine.pending
             if d.operator_id == 'interval-join']
    expected = [n+1 for n in range(count) if abs(n-count//2) <= 2]
    windows = [json.loads(d.payload) for d in engine.pending
               if d.operator_id != 'interval-join']
    assert pairs == expected
    assert len(windows) == 2
    assert all(row['count'] == count and row['sum'] == count for row in windows)
    assert not engine.state and not engine.join
    indexed = hasattr(engine, 'join_candidates_examined')
    checks.append({
        'join_pairs': len(pairs), 'window_results': len(windows),
        'candidate_checks': engine.join_candidates_examined if indexed
                            else count*(count-1)//2+count,
        'counter_scope': 'engine diagnostic' if indexed else 'full-scan formula',
    })
print(json.dumps({
    'processing_seconds': timings, 'median_seconds': statistics.median(timings),
    'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
    'checks': checks,
}))
"""


def probe(source: Path, records: int, repetitions: int) -> dict[str, object]:
    return json.loads(
        subprocess.check_output(
            [sys.executable, "-c", PROBE, str(source), str(records), str(repetitions)],
            text=True,
            timeout=120,
        )
    )


def historical_probe(ref: str, records: int, repetitions: int) -> tuple[str, dict[str, object]]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
        cwd=REPOSITORY,
        text=True,
    ).strip()
    files = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", commit, "--", PREFIX],
        cwd=REPOSITORY,
        text=True,
    ).splitlines()
    if not files:
        raise ValueError("revision has no Current source tree")
    with tempfile.TemporaryDirectory(prefix="current-baseline-") as folder:
        exported = Path(folder)
        for name in files:
            target = exported / name.removeprefix(PREFIX)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=REPOSITORY)
            )
        return commit, probe(exported, records, repetitions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=12_000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--baseline", help="Trusted historical Git revision to execute for comparison"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.records, args.repetitions) < 1:
        parser.error("records and repetitions must be positive")
    if not sys.platform.startswith("linux"):
        parser.error("this focused probe records Linux resource accounting")
    before = provenance(1729, "focused-join")
    before.update(
        seed=None,  # The focused input is deterministic and uses no random generator.
        dataset_id=hashlib.sha256(PROBE.encode() + str(args.records).encode()).hexdigest(),
        warmup_runs=0,
        measurement_runs=args.repetitions,
    )
    report = {
        "schema_version": 1,
        "scenario": "same-key readings without watermarks, one sparse metadata probe, then end",
        "records": args.records + 2,
        "repetitions": args.repetitions,
        "source": before,
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(PROBE.encode()).hexdigest(),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Engine.apply elapsed time; Record creation/imports excluded; process RSS includes all probe allocations",
        "limits": "Synthetic comparison on a shared machine, not a standard workload or production capacity claim",
    }
    if args.baseline:
        commit, baseline = historical_probe(args.baseline, args.records, args.repetitions)
        report.update(baseline_commit=commit, baseline=baseline)
    report["indexed"] = probe(PROJECT / "src", args.records, args.repetitions)
    after = provenance(1729, "focused-join")
    if before["source_content_sha256"] != after["source_content_sha256"]:
        raise RuntimeError("source changed during the focused probe")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
