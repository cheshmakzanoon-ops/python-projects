"""Named gates complement the adversarial and generated regression suites."""

from pathlib import Path

from pp_routecraft import SearchBudget, Status, exhaustive, solve, verify
from pp_routecraft.benchmark import run_benchmark
from pp_routecraft.fixtures import tiny
from pp_routecraft.reporting.report import output_directory


def test_rc01_six_customer_complete_enumeration() -> None:
    from pp_routecraft import RoutingInstance, Stop, Vehicle

    # Every off-diagonal directed arc costs one: any one-vehicle tour costs seven.
    instance = RoutingInstance(
        tuple(Stop(j, 1) for j in range(1, 7)),
        (Vehicle(0, 6), Vehicle(1, 6)),
        tuple(tuple(int(i != j) for j in range(7)) for i in range(7)),
    )
    reference = exhaustive(instance)
    result = solve(instance, SearchBudget(40))
    assert reference.status == Status.OPTIMAL
    assert reference.iterations == 720 * 7
    assert reference.plan is not None and result.plan is not None
    assert reference.plan.objective == result.plan.objective == (1, 7)


def test_rc06_equal_budget_ci_publishes_every_trial(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[2]
    report = run_benchmark("ci", output_directory(tmp_path / "benchmark"), 1729, project)
    assert report["status"] == "passed"
    import json

    saved = json.loads((tmp_path / "benchmark" / "benchmark.json").read_text())
    assert saved["measurement_runs"] == 5
    assert len(saved["metrics"]["cases"]) == 2
    # The separate exact-optimal control must exercise real work and publish
    # measured non-improvement even when every full-scale scenario improves.
    assert saved["correctness_checks"]["no_improvement_control"]
    assert len(saved["metrics"]["controls"]) == 1
    control = saved["metrics"]["controls"][0]
    assert control["name"] == "exact_optimal_construction_baseline"
    assert control["warmup_runs"] == 1 and control["measurement_runs"] == 5
    assert control["paired_outcomes"] == ["tie"] * 5
    assert control["no_improvement_trials"] == 5
    assert control["all_plans_independently_verified"]
    assert control["oracle"]["status"] == "OPTIMAL"
    assert control["oracle"]["objective"] == [1, 8]
    assert control["oracle"]["iterations"] == 24
    from pp_routecraft.reporting.serialization import instance_from_dict, plan_from_dict

    oracle_instance = instance_from_dict(control["instance"])
    oracle_plan = plan_from_dict(control["oracle_plan"])
    assert verify(oracle_instance, oracle_plan).valid
    assert oracle_plan.objective == (1, 8)
    assert len(control["baseline"]) == len(control["search"]) == 5
    for row in control["baseline"] + control["search"]:
        assert row["objective"] == [1, 8]
        assert row["iterations"] == control["budget"]["iterations"] == 20
        assert sum(count for _, count in row["operator_counts"]) == 20
        assert row["stopping_reason"] == "iteration_budget"
        assert row["first_feasible_seconds"] is not None
    for case in saved["metrics"]["cases"]:
        assert len(case["paired_outcomes"]) == len(case["baseline"]) == len(case["search"]) == 5
        assert all(
            outcome in ("gain", "tie", "loss", "unavailable") for outcome in case["paired_outcomes"]
        )
        assert all(row["iterations"] <= case["budget"]["iterations"] for row in case["search"])


def test_rc08_status_distinction() -> None:
    instance = tiny(impossible=True)
    result = solve(instance, SearchBudget(0))
    assert result.status == Status.NO_FEASIBLE_PLAN_FOUND
    assert result.plan is None
    assert exhaustive(instance).status == Status.PROVEN_INFEASIBLE
    valid = solve(tiny(), SearchBudget(0))
    assert valid.plan is not None and verify(tiny(), valid.plan).valid


def test_rc06_control_rejects_valid_but_suboptimal_baseline(monkeypatch) -> None:
    from dataclasses import replace

    import pytest

    from pp_routecraft import Plan, Route
    from pp_routecraft import benchmark as benchmark_module

    # Each route costs 8 (2+2+4 and 6+2), but using two vehicles is worse
    # than the independently known one-vehicle tour with objective (1,8).
    inferior = Plan((Route(0, (1, 2)), Route(1, (3,))), (2, 16))
    assert verify(tiny(), inferior).valid
    original = solve(tiny(), SearchBudget(0))
    measured = replace(original, plan=inferior)
    monkeypatch.setattr(benchmark_module, "construction_baseline", lambda *args: measured)
    with pytest.raises(RuntimeError, match="match exhaustive optimum"):
        benchmark_module.non_improvement_control(1729)
