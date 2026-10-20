"""Nonmetric frozen-prefix repair and stop observations at the final boundary."""

from unittest.mock import patch

import pytest

from pp_routecraft import (
    LoadedJob,
    Plan,
    Route,
    RoutingInstance,
    SearchBudget,
    Stop,
    Vehicle,
    VehicleState,
    construct,
    prepare_replan,
    solve,
    verify,
)
from pp_routecraft.benchmark import construction_baseline
from pp_routecraft.fixtures import tiny


def test_infeasible_partial_depot_return_does_not_discard_valid_onboard_continuation() -> None:
    instance = RoutingInstance(
        (Stop(1, 1), Stop(2, 1)),
        (Vehicle(0, 2, end=10),),
        ((0, 1, 20), (100, 0, 1), (1, 20, 0)),
    )
    previous = Plan((Route(0, (1, 2)),), (1, 3))
    assert verify(instance, previous).valid
    state = VehicleState(0, True, (1,), 1, 1, 1, (LoadedJob(2, 1),), "service_complete")
    rolling = prepare_replan(instance, previous, instance, (state,))
    result = solve(rolling, SearchBudget(20))
    assert result.plan is not None
    assert result.plan.objective == (1, 3)
    assert verify(rolling, result.plan).valid
    assert result.plan.routes[0].stops == (1, 2)


@pytest.mark.parametrize("phase", ["construction", "last_iteration", "initial_zero_budget"])
@pytest.mark.parametrize("cause", ["cancelled", "wall_clock"])
def test_stop_after_final_atomic_operation_is_reported(phase: str, cause: str) -> None:
    incumbent = construct(tiny())
    assert incumbent is not None
    stopped = phase == "initial_zero_budget"
    now = 2.0 if stopped else 0.0

    def complete(*args: object, **kwargs: object):
        nonlocal stopped, now
        stopped, now = True, 2.0
        return incumbent

    times = [0.0]
    with (
        patch(
            "pp_routecraft.search.solver.time.monotonic",
            side_effect=lambda: times.pop() if times else now,
        ),
        patch("pp_routecraft.search.solver.construct", side_effect=complete),
        patch("pp_routecraft.search.solver.relocate", side_effect=complete),
        patch("random.Random.choices", return_value=[0]),
    ):
        result = solve(
            tiny(),
            SearchBudget(
                1 if phase == "last_iteration" else 0, 1.0 if cause == "wall_clock" else None
            ),
            initial=incumbent if phase != "construction" else None,
            cancelled=(lambda: stopped) if cause == "cancelled" else None,
        )
    assert result.stopping_reason == cause
    assert result.iterations == (1 if phase == "last_iteration" else 0)
    assert result.plan == incumbent
    assert verify(tiny(), result.plan).valid


def test_comparison_baseline_reports_a_deadline_crossed_by_its_final_construction() -> None:
    incumbent = construct(tiny())
    assert incumbent is not None
    now = 0.0

    def complete(*args: object, **kwargs: object):
        nonlocal now
        now = 2.0
        return incumbent

    with (
        patch("pp_routecraft.benchmark.time.monotonic", side_effect=lambda: now),
        patch("pp_routecraft.benchmark.construct", side_effect=complete),
    ):
        result = construction_baseline(tiny(), SearchBudget(0, 1.0), 1729)
    assert result.stopping_reason == "wall_clock"
    assert result.iterations == 0 and result.plan == incumbent
