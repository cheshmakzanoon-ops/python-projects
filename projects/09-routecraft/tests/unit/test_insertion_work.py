"""A dense feasible route must not be fully scheduled at every candidate position."""

from unittest.mock import patch

from pp_routecraft import RoutingInstance, Stop, Vehicle, construct, verify
from pp_routecraft.construction.insertion import evaluate_route


def test_construction_scheduling_work_is_quadratic_for_a_feasible_route() -> None:
    count = 80
    instance = RoutingInstance(
        tuple(Stop(node, 1) for node in range(1, count + 1)),
        (Vehicle(0, count),),
        tuple(tuple(int(a != b) for b in range(count + 1)) for a in range(count + 1)),
    )
    visits = calls = 0

    def measured(instance: RoutingInstance, index: int, jobs: tuple[int, ...]):
        nonlocal visits, calls
        calls += 1
        visits += len(jobs)
        return evaluate_route(instance, index, jobs)

    with patch("pp_routecraft.construction.insertion.evaluate_route", side_effect=measured):
        plan = construct(instance, regret=False)
    assert plan is not None and verify(instance, plan).valid
    assert plan.objective == (1, count + 1)
    assert calls <= 2 * count + 4
    assert visits <= 2 * count * count
