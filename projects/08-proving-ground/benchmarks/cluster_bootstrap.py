"""Bounded five-repeat asset-bootstrap workload; records work, never asserts timing."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from pp_proving_ground.evaluation.metrics import asset_bootstrap

BASELINE = "39d3a8d4be3e8e2e7de85379790d68f5367d6825"


class WorkCounter:
    """Observe only algorithm-owned calls; numerical libraries retain their own NumPy."""

    def __init__(self, probability: np.ndarray[Any, Any]):
        self.probability = probability
        self.work = {
            "membership_scan_values": 0,
            "expanded_row_indices": 0,
            "direct_score_orders": 0,
            "sklearn_average_precision_calls": 0,
        }

    def __getattr__(self, name: str) -> Any:
        return getattr(np, name)

    def flatnonzero(self, value: Any) -> Any:
        self.work["membership_scan_values"] += len(value)
        return np.flatnonzero(value)

    def concatenate(self, values: Any) -> Any:
        self.work["expanded_row_indices"] += sum(len(value) for value in values)
        return np.concatenate(values)

    def unique(self, value: Any, **kwargs: Any) -> Any:
        if value is self.probability:
            self.work["direct_score_orders"] += 1
        return np.unique(value, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--assets", type=int, default=2000)
    parser.add_argument("--repetitions", type=int, default=32)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists():
        raise ValueError("output must be an absolute fresh file")
    if not 100 <= args.rows <= 100000 or not 2 <= args.assets <= min(args.rows, 10000):
        raise ValueError("bounded workload requires 100..100000 rows and 2..10000 assets")
    if not 1 <= args.repetitions <= 100 or not 1 <= args.runs <= 5:
        raise ValueError("bounded workload permits 1..100 bootstrap repetitions and 1..5 runs")
    rng = np.random.default_rng(1729)
    assets = (np.arange(args.rows, dtype=np.int64) % args.assets) - 7
    rng.shuffle(assets)
    probability = rng.integers(0, 97, size=args.rows).astype(np.float64) / 96
    labels = (rng.random(args.rows) < probability).astype(np.int64)
    input_hash = hashlib.sha256()
    for value in (labels, probability, assets):
        input_hash.update(value.tobytes())
    namespace = asset_bootstrap.__globals__
    original_np = namespace["np"]
    original_ap = namespace.get("average_precision_score")
    measurements = []
    for _ in range(args.runs):
        counter = WorkCounter(probability)
        namespace["np"] = counter
        if original_ap is not None:

            def counted_ap(*values: Any, **kwargs: Any) -> Any:
                counter.work["sklearn_average_precision_calls"] += 1
                return original_ap(*values, **kwargs)

            namespace["average_precision_score"] = counted_ap
        try:
            started = time.perf_counter()
            report = asset_bootstrap(labels, probability, assets, 113, args.repetitions)
            elapsed = time.perf_counter() - started
        finally:
            namespace["np"] = original_np
            if original_ap is not None:
                namespace["average_precision_score"] = original_ap
        assert report["defined_repetitions"] == args.repetitions
        interval = report["pr_auc_95_percentile"]
        assert len(interval) == 2 and 0 <= interval[0] <= interval[1] <= 1
        measurements.append({"seconds": elapsed, "work": counter.work, "report": report})
    assert all(item["report"] == measurements[0]["report"] for item in measurements)
    module = Path(inspect.getfile(asset_bootstrap)).resolve()
    result = {
        "format_version": 1,
        "scope": "asset bootstrap only; no fitting, disk artifacts, serving, or full lifecycle",
        "caller_source_label": args.source_label,
        "baseline_comparison_revision": BASELINE,
        "workload_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "algorithm_module": str(module),
        "algorithm_module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "python": sys.version,
        "platform": platform.platform(),
        "parameters": {
            "rows": args.rows,
            "assets": args.assets,
            "score_levels": 97,
            "input_seed": 1729,
            "bootstrap_seed": 113,
            "repetitions": args.repetitions,
            "runs": args.runs,
            "warmup_runs": 0,
        },
        "input_sha256": input_hash.hexdigest(),
        "measurements": measurements,
        "median_seconds": statistics.median(item["seconds"] for item in measurements),
        "timing_assertion": False,
        "work_interpretation": "membership scans and row expansion count only calls owned by the selected algorithm; library-internal work is excluded. Legacy sklearn AP sorts scores once per call; new direct tied-score ordering occurs once.",
        "limitations": [
            "working-tree run, not immutable final-commit certification",
            "shared host timings are descriptive",
            "correctness is independently tested with exact tiny threshold models",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "median_seconds": result["median_seconds"],
                "work": measurements[0]["work"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
