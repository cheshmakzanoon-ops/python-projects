"""Controlled insertion-module comparison using one current support package.

The pinned historical insertion module imports the current package's domain and
validation modules. This is not a complete historical-package comparison. Timings
are diagnostic; work counters and plan equality are portable checks. This command
never overwrites an existing report.
"""

import argparse
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import ModuleType

import pp_routecraft
from pp_routecraft import RoutingInstance, Vehicle, verify
from pp_routecraft.construction import insertion
from pp_routecraft.fixtures import island

BASELINE_COMMIT = "39d3a8d4be3e8e2e7de85379790d68f5367d6825"
BASELINE_SHA256 = "12eb2cb042c2d05a85c31f10a81157fe53f83638bfbc9bfba718e392c19eb883"


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer")
    return parsed


def source_digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(
        [
            *root.glob("src/**/*.py"),
            *root.glob("tests/**/*.py"),
            root / "pyproject.toml",
            root / "uv.lock",
            root / ".python-version",
        ]
    ):
        value.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return value.hexdigest()


def imported_package_digest(package: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_file() and (path.suffix == ".py" or path.name == "py.typed"):
            value.update(path.relative_to(package).as_posix().encode() + b"\0" + path.read_bytes())
    return value.hexdigest()


def instance_digest(instance: RoutingInstance) -> str:
    encoded = json.dumps(asdict(instance), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_baseline(path: Path) -> ModuleType:
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASELINE_SHA256:
        raise ValueError("baseline file differs from the reviewed historical module")
    spec = importlib.util.spec_from_file_location("routecraft_baseline_insertion", path)
    if spec is None or spec.loader is None:
        raise ValueError("baseline must be a Python source file")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def trial(module: ModuleType, instance: RoutingInstance, *, regret: bool = False):
    original = module.evaluate_route
    work = {"schedule_calls": 0, "scheduled_customer_visits": 0}

    def counted(instance, index, jobs):
        work["schedule_calls"] += 1
        work["scheduled_customer_visits"] += len(jobs)
        return original(instance, index, jobs)

    module.evaluate_route = counted
    try:
        started = time.perf_counter()
        plan = module.construct(instance, regret=regret)
        elapsed = time.perf_counter() - started
    finally:
        module.evaluate_route = original
    if plan is None or not verify(instance, plan).valid:
        raise AssertionError("construction returned a missing/invalid plan")
    return plan, {"elapsed_seconds": elapsed, **work}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=positive_integer, default=5)
    args = parser.parse_args()
    baseline = load_baseline(args.baseline_file)
    root = Path(__file__).resolve().parents[1]
    before = source_digest(root)
    package = Path(pp_routecraft.__file__).resolve().parent
    package_before = imported_package_digest(package)
    insertion_path = Path(insertion.__file__).resolve()
    warmup = island(12)
    for module in (baseline, insertion):
        trial(module, warmup)
    rows = []
    for count in (40, 80, 160):
        instance = island(count, 1729)
        instance = replace(
            instance,
            stops=tuple(replace(stop, due=1_000_000) for stop in instance.stops),
            vehicles=(Vehicle(0, 3 * count, end=1_000_000),),
        )
        results = {"baseline": [], "revised": []}
        for repetition in range(args.repetitions):
            plans = {}
            order = [("baseline", baseline), ("revised", insertion)]
            if repetition % 2:
                order.reverse()
            for name, module in order:
                plan, measurement = trial(module, instance)
                results[name].append(measurement)
                plans[name] = plan
            if plans["baseline"] != plans["revised"]:
                raise AssertionError("paired construction plans differ")
        rows.append(
            {
                "customers": count,
                "regret": False,
                "repetitions": len(results["baseline"]),
                "instance_sha256": instance_digest(instance),
                "objective": plans["revised"].objective,
                "plans_identical": True,
                **results,
            }
        )
    regret_instance = island(40, 1730)
    first, first_work = trial(baseline, regret_instance, regret=True)
    second, second_work = trial(insertion, regret_instance, regret=True)
    if (
        first != second
        or source_digest(root) != before
        or imported_package_digest(package) != package_before
        or hashlib.sha256(args.baseline_file.read_bytes()).hexdigest() != BASELINE_SHA256
    ):
        raise AssertionError("regret control or measured-source stability check failed")
    report = {
        "schema_version": 1,
        "kind": "paired-construction-diagnostic",
        "scope": "Controlled algorithm-module comparison: pinned historical insertion module and current insertion module share the imported current support package. Not a complete historical-package comparison or standard workload; host isolation is not established by this driver.",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "seed": 1729,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--", "."], cwd=root, text=True
            ).strip()
        ),
        "source_scope": "driver checkout Python source/tests, pyproject.toml, uv.lock, .python-version; relative path + NUL + bytes. Actual imported package is recorded separately.",
        "source_content_sha256": before,
        "source_checkout_path": str(root),
        "imported_package": {
            "path": str(package),
            "content_sha256": package_before,
            "hash_scope": "all .py and py.typed files; relative path + NUL + bytes",
            "shared_by": ["historical insertion module", "current insertion module"],
        },
        "current_insertion_module": {
            "path": str(insertion_path),
            "sha256": hashlib.sha256(insertion_path.read_bytes()).hexdigest(),
        },
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_unchanged": True,
        "baseline_commit": BASELINE_COMMIT,
        "baseline_file_sha256": BASELINE_SHA256,
        "baseline_file_path": str(args.baseline_file.resolve()),
        "baseline_scope": "only construction/insertion.py from the pinned commit; its package imports use the recorded current support package",
        "parameters": {
            "customers": [40, 80, 160],
            "single_vehicle": True,
            "capacity_per_customer": 3,
            "due_and_shift_end": 1000000,
            "repetitions": args.repetitions,
            "measured_pairs": sum(len(row["baseline"]) for row in rows),
            "warmup_customers": 12,
            "warmup_seed": 1729,
            "warmup_instance_sha256": instance_digest(warmup),
            "threads": 1,
            "regret": False,
        },
        "work_counter_scope": "Complete optimizer route schedule calls/customer visits; excludes candidate certificate arithmetic, profile building, verification and allocation costs.",
        "cases": rows,
        "regret_control": {
            "customers": 40,
            "seed": 1730,
            "repetitions": 1,
            "instance_sha256": instance_digest(regret_instance),
            "plans_identical": True,
            "baseline": first_work,
            "revised": second_work,
        },
        "correctness_checks": {
            "all_plans_independently_verified": True,
            "all_paired_plans_identical": True,
            "source_unchanged": True,
            "imported_package_unchanged": True,
            "pinned_baseline_unchanged": True,
        },
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for row in rows:
        print(
            row["customers"],
            {
                name: statistics.median(run["elapsed_seconds"] for run in row[name])
                for name in ("baseline", "revised")
            },
        )


if __name__ == "__main__":
    main()
