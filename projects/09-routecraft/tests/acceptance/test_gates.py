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
