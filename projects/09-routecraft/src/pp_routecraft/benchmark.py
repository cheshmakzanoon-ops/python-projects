"""Seeded equal-budget comparison; all unsuccessful trials remain in the report."""

import hashlib
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

from pp_routecraft.construction.insertion import construct
from pp_routecraft.domain.instance import RoutingInstance, SearchBudget, SolveResult, Status
from pp_routecraft.fixtures import island, new_request, tiny
from pp_routecraft.reference.exhaustive import exhaustive
from pp_routecraft.reporting.report import provenance, write_json
from pp_routecraft.reporting.serialization import instance_dict
from pp_routecraft.search.solver import solve
from pp_routecraft.validation.verifier import verify


def construction_baseline(
    instance: RoutingInstance, budget: SearchBudget, seed: int
) -> SolveResult:
    """Greedy/regret construction restarts under the same allowed effort caps.

    First attempt is greedy; seeded job-order restarts are added afterwards.
    Construction is atomic; wall-time checks are at restart boundaries.
    """
    started = time.monotonic()
    best = None
    first = None
    attempts = 0
    reason = "iteration_budget"
    trajectory = []
    for iteration in range(budget.iterations + 1):
        if budget.seconds is not None and time.monotonic() - started >= budget.seconds:
            reason = "wall_clock"
            break
        plan = construct(instance, regret=False, seed=None if iteration == 0 else seed + iteration)
        if iteration:
            attempts += 1
        if plan is not None and verify(instance, plan).valid:
            if first is None:
                first = time.monotonic() - started
            if best is None or plan.objective < best.objective:
                best = plan
                trajectory.append((iteration, *plan.objective))
    if budget.seconds is not None and time.monotonic() - started >= budget.seconds:
        reason = "wall_clock"
    return SolveResult(
        Status.FEASIBLE if best else Status.NO_FEASIBLE_PLAN_FOUND,
        best,
        attempts,
        reason,
        time.monotonic() - started,
        first,
        tuple(trajectory),
        (("construction_restarts", attempts),),
    )


def _peak_rss() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    scale = 1 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale


def _measurement(result: SolveResult) -> dict[str, object]:
    row = {key: value for key, value in asdict(result).items() if key != "plan"}
    row["objective"] = result.plan.objective if result.plan else None
    return row


def non_improvement_control(seed: int) -> dict[str, object]:
    """Measure a real saturated baseline, with an independently proved optimum.

    This separate tiny control cannot improve because greedy already attains the
    exhaustive optimum. Both algorithms still execute their full iteration budget;
    no trial outcome or solver status is substituted with a known answer.
    """
    instance = tiny()
    oracle = exhaustive(instance)
    if (
        oracle.status != Status.OPTIMAL
        or oracle.plan is None
        or not verify(instance, oracle.plan).valid
    ):
        raise RuntimeError("non-improvement control requires an independently verified optimum")
    optimum = oracle.plan.objective
    budget = SearchBudget(20)

    def trial(trial_seed: int) -> tuple[SolveResult, SolveResult]:
        baseline = construction_baseline(instance, budget, trial_seed)
        searched = solve(instance, budget, seed=trial_seed)
        for result in (baseline, searched):
            if result.plan is None or not verify(instance, result.plan).valid:
                raise RuntimeError("non-improvement control produced an invalid or missing plan")
            if result.plan.objective != optimum:
                raise RuntimeError("non-improvement control failed to match exhaustive optimum")
        return baseline, searched

    warmup_baseline, warmup_search = trial(seed)
    baseline_runs: list[SolveResult] = []
    search_runs: list[SolveResult] = []
    outcomes: list[str] = []
    for repetition in range(5):
        baseline, searched = trial(seed + repetition)
        baseline_runs.append(baseline)
        search_runs.append(searched)
        # Derive comparisons from the measured, independently checked plans.
        assert baseline.plan is not None and searched.plan is not None
        outcomes.append(
            "gain"
            if searched.plan.objective < baseline.plan.objective
            else "tie"
            if searched.plan.objective == baseline.plan.objective
            else "loss"
        )
    serialized_instance = instance_dict(instance)
    input_digest = hashlib.sha256(
        json.dumps(serialized_instance, sort_keys=True).encode()
    ).hexdigest()
    return {
        "name": "exact_optimal_construction_baseline",
        "purpose": "non-improvement control; separate from full-scale island scenarios",
        "dataset_id": "tiny-directed-v1:" + input_digest,
        "instance": serialized_instance,
        "seed": seed,
        "budget": asdict(budget),
        "warmup_runs": 1,
        "measurement_runs": 5,
        "oracle": _measurement(oracle),
        "oracle_plan": asdict(oracle.plan),
        "oracle_verified": True,
        "warmup": {
            "baseline": _measurement(warmup_baseline),
            "search": _measurement(warmup_search),
        },
        "baseline": [_measurement(result) for result in baseline_runs],
        "search": [_measurement(result) for result in search_runs],
        "paired_outcomes": outcomes,
        "no_improvement_trials": sum(outcome != "gain" for outcome in outcomes),
        "all_plans_independently_verified": True,
    }


def run_benchmark(profile: str, output: Path, seed: int, project: Path) -> dict[str, object]:
    before = provenance(project)
    rows: list[dict[str, object]] = []
    tiers = (25,) if profile == "ci" else (25, 100, 500)
    seeds = (seed,) if profile == "ci" else (seed, seed + 1, seed + 2)
    dataset_hash = hashlib.sha256()
    for n in tiers:
        for scenario_seed in seeds:
            for tight in (False, True):
                instance = island(n, scenario_seed, tight=tight)
                dataset_hash.update(json.dumps(instance_dict(instance), sort_keys=True).encode())
                budget = SearchBudget(
                    20 if profile == "ci" else 60, 0.4 if n == 25 else 2.0 if n == 100 else 8.0
                )
                # One real warm-up per algorithm, separate from measured trials.
                construction_baseline(instance, budget, scenario_seed)
                solve(instance, budget, seed=scenario_seed)
                baseline_runs: list[SolveResult] = []
                search_runs: list[SolveResult] = []
                verifier_seconds: list[float] = []
                for repetition in range(5):
                    baseline_runs.append(
                        construction_baseline(instance, budget, scenario_seed + repetition)
                    )
                    search = solve(instance, budget, seed=scenario_seed + repetition)
                    search_runs.append(search)
                    if search.plan is not None:
                        start = time.perf_counter()
                        assert verify(instance, search.plan).valid
                        verifier_seconds.append(time.perf_counter() - start)
                row: dict[str, object] = {
                    "customers": n,
                    "seed": scenario_seed,
                    "tight_windows": tight,
                    "budget": asdict(budget),
                    "baseline": [_measurement(r) for r in baseline_runs],
                    "search": [_measurement(r) for r in search_runs],
                    "baseline_feasible_rate": sum(r.plan is not None for r in baseline_runs) / 5,
                    "search_feasible_rate": sum(r.plan is not None for r in search_runs) / 5,
                    "verifier_seconds_median": statistics.median(verifier_seconds)
                    if verifier_seconds
                    else None,
                }
                # Compare paired measurements, including ties and regressions.
                outcomes = []
                for base, search in zip(baseline_runs, search_runs, strict=True):
                    outcomes.append(
                        "unavailable"
                        if base.plan is None or search.plan is None
                        else "gain"
                        if search.plan.objective < base.plan.objective
                        else "tie"
                        if search.plan.objective == base.plan.objective
                        else "loss"
                    )
                row["paired_outcomes"] = outcomes
                rows.append(row)
    exact_ok = True
    for impossible in (False, True):
        instance = tiny(impossible=impossible)
        exact = exhaustive(instance)
        exact_ok &= exact.status == (Status.PROVEN_INFEASIBLE if impossible else Status.OPTIMAL)
    control = non_improvement_control(seed)
    control_ok = (
        control["oracle_verified"] is True
        and control["all_plans_independently_verified"] is True
        and control["no_improvement_trials"] == 5
    )
    original = island(25, seed)
    original_result = solve(original, SearchBudget(20), seed=seed)
    replanning_ok = False
    if original_result.plan:
        updated = new_request(original, original_result.plan)
        result = solve(updated, SearchBudget(20), seed=seed)
        replanning_ok = result.plan is not None and verify(updated, result.plan).valid
    after = provenance(project)
    stable = (
        before["source_content_sha256"] == after["source_content_sha256"]
        and before["root_contract_sha256"] == after["root_contract_sha256"]
    )
    result_report: dict[str, object] = {
        "schema_version": 1,
        "project": "routecraft",
        **before,
        "seed": seed,
        "dataset_id": "island-v1:" + dataset_hash.hexdigest(),
        "profile": profile,
        "parameters": {
            "tiers": tiers,
            "seeds": seeds,
            "threads": 1,
            "processes": 1,
            "budget_semantics": "identical wall-clock and iteration caps, one initial constructor; baseline iterations are construction restarts, search iterations are neighborhoods; atomic operations may overrun wall cap",
        },
        "warmup_runs": 1,
        "measurement_runs": 5,
        "metrics": {
            "cases": rows,
            "controls": [control],
            "process_peak_rss_bytes": _peak_rss(),
            "memory_scope": "Linux process cumulative peak RSS, includes warmups and rendering imports",
        },
        "correctness_checks": {
            "tiny_exact": exact_ok,
            "no_improvement_control": control_ok,
            "replanning": replanning_ok,
            "source_stable": stable,
            "all_search_trials_feasible": all(row["search_feasible_rate"] == 1.0 for row in rows),
        },
        "status": "passed"
        if exact_ok
        and control_ok
        and replanning_ok
        and stable
        and all(row["search_feasible_rate"] == 1.0 for row in rows)
        else "failed",
    }
    write_json(output / "benchmark.json", result_report)
    return result_report
