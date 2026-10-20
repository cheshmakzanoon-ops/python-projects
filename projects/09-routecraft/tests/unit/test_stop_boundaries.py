"""Cancellation and deadline observations stop at the next completed operation."""

from unittest.mock import patch

import pytest

from pp_routecraft import SearchBudget, Status, construct, solve
from pp_routecraft.fixtures import tiny


def test_preconstruction_cancellation_is_latched() -> None:
    observations = iter((True, False))
    with patch("pp_routecraft.search.solver.construct") as constructor:
        result = solve(tiny(), SearchBudget(10), cancelled=lambda: next(observations, False))
    assert result.status == Status.NO_FEASIBLE_PLAN_FOUND
    assert result.stopping_reason == "cancelled"
    assert result.iterations == 0
    constructor.assert_not_called()


@pytest.mark.parametrize("cause", ["cancelled", "wall_clock"])
def test_failed_construction_checks_stop_before_fallback(cause: str) -> None:
    stopped = False
    now = 0.0

    def constructor(*args: object, **kwargs: object) -> None:
        nonlocal stopped, now
        stopped = True
        now = 10.0

    with (
        patch("pp_routecraft.search.solver.construct", side_effect=constructor) as call,
        patch("pp_routecraft.search.solver.time.monotonic", side_effect=lambda: now),
    ):
        result = solve(
            tiny(),
            SearchBudget(10, 1.0 if cause == "wall_clock" else None),
            cancelled=(lambda: stopped) if cause == "cancelled" else None,
        )
    assert result.stopping_reason == cause
    assert result.iterations == 0
    assert result.plan is None
    assert call.call_count == 1


def test_completed_construction_retains_incumbent_when_cancelled() -> None:
    incumbent = construct(tiny())
    assert incumbent is not None
    stopped = False

    def constructor(*args: object, **kwargs: object):
        nonlocal stopped
        stopped = True
        return incumbent

    with patch("pp_routecraft.search.solver.construct", side_effect=constructor) as call:
        result = solve(tiny(), SearchBudget(10), cancelled=lambda: stopped)
    assert result.stopping_reason == "cancelled"
    assert result.iterations == 0
    assert result.plan == incumbent
    assert call.call_count == 1
