"""RC-04/05: reproducible effort, independent incumbent validation, stop semantics."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from pp_routecraft import Plan, Route, SearchBudget, Status, construct, solve, verify
from pp_routecraft.construction.insertion import evaluate_route
from pp_routecraft.fixtures import island, tiny
from pp_routecraft.neighborhoods.moves import destroy_repair, relocate, reverse_segment, swap


def test_reference_objective_and_truthful_unknown() -> None:
    from pp_routecraft import exhaustive

    exact = exhaustive(tiny())
    heuristic = solve(tiny(), SearchBudget(100))
    assert exact.status == Status.OPTIMAL
    assert exact.plan is not None and heuristic.plan is not None
    assert exact.plan.objective == heuristic.plan.objective == (1, 8)
    assert heuristic.status == Status.FEASIBLE
    assert heuristic.optimality_gap == "unknown"
    impossible = tiny(impossible=True)
    assert exhaustive(impossible).status == Status.PROVEN_INFEASIBLE
    assert solve(impossible, SearchBudget(5)).status == Status.NO_FEASIBLE_PLAN_FOUND


def test_same_seed_iteration_result_repeats() -> None:
    instance = island(25)
    a = solve(instance, SearchBudget(80), seed=67)
    b = solve(instance, SearchBudget(80), seed=67)
    assert a.plan == b.plan
    assert a.trajectory == b.trajectory
    assert a.operator_counts == b.operator_counts
    assert a.iterations == b.iterations == 80
    assert sum(count for _, count in a.operator_counts) == 80
    assert a.stopping_reason == "iteration_budget"
    assert list(a.trajectory) == sorted(a.trajectory, key=lambda row: row[0])
    assert [row[1:] for row in a.trajectory] == sorted(
        [row[1:] for row in a.trajectory], reverse=True
    )


def test_cancel_timeout_rejected_moves_keep_incumbent() -> None:
    instance = tiny()
    incumbent = construct(instance)
    assert incumbent is not None
    cancelled = solve(instance, SearchBudget(100), initial=incumbent, cancelled=lambda: True)
    timed_out = solve(instance, SearchBudget(100, 0), initial=incumbent)
    assert cancelled.stopping_reason == "cancelled" and cancelled.iterations == 0
    assert timed_out.stopping_reason == "wall_clock" and timed_out.iterations == 0
    assert cancelled.plan == timed_out.plan == incumbent
    bad = Plan((Route(0, (1, 1)),), (1, 0))
    with (
        patch("pp_routecraft.search.solver.relocate", return_value=bad),
        patch("random.Random.choices", return_value=[0]),
    ):
        result = solve(instance, SearchBudget(10), initial=incumbent)
    assert result.plan == incumbent
    assert verify(instance, result.plan).valid


def test_cancel_after_progress() -> None:
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 7

    result = solve(island(25), SearchBudget(100), cancelled=cancel)
    assert result.stopping_reason == "cancelled"
    assert 1 <= result.iterations <= 7
    assert result.plan is not None and verify(island(25), result.plan).valid


def test_preconstruction_deadline_and_cancel_are_unknown() -> None:
    for result in (solve(tiny(), SearchBudget(10, 0)), solve(tiny(), cancelled=lambda: True)):
        assert result.plan is None
        assert result.status == Status.NO_FEASIBLE_PLAN_FOUND


@pytest.mark.parametrize(
    "budget", [SearchBudget(-1), SearchBudget(1, -1), SearchBudget(1, float("inf"))]
)
def test_invalid_budgets(budget: SearchBudget) -> None:
    assert solve(tiny(), budget).status == Status.INVALID_INPUT


def test_invalid_instance_and_incumbent() -> None:
    assert solve(replace(tiny(), depot=2)).status == Status.INVALID_INPUT
    bad = Plan((Route(0, (1,)),), (1, 9))
    assert solve(tiny(), initial=bad).status == Status.INVALID_INPUT


def test_directed_route_recalculation() -> None:
    instance = replace(
        tiny(),
        vehicles=tuple(replace(v, end=100) for v in tiny().vehicles),
        stops=tuple(replace(s, due=100) for s in tiny().stops),
    )
    forward = evaluate_route(instance, 0, (1, 2, 3))
    backward = evaluate_route(instance, 0, (3, 2, 1))
    assert forward is not None and backward is not None
    assert forward[1] == 8 and backward[1] == 30
    assert [v.arrival for v in backward[0].schedule] == [6, 14, 23]
    assert backward[0].return_time == 30


def test_moves_feasibility_and_budget_independence() -> None:
    import random

    instance = island(25)
    incumbent = construct(instance)
    assert incumbent is not None
    for seed in range(12):
        for operator in (relocate, swap, reverse_segment):
            candidate = operator(instance, incumbent, random.Random(seed))
            assert candidate is None or verify(instance, candidate).valid
        for related in (False, True):
            candidate = destroy_repair(instance, incumbent, random.Random(seed), related=related)
            assert candidate is None or verify(instance, candidate).valid
