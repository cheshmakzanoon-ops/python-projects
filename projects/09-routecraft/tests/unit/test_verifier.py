"""RC-01/02/03: hand-derived costs and independently recomputed hard constraints."""

from dataclasses import replace

import pytest

from pp_routecraft import (
    Plan,
    Route,
    RoutingInstance,
    Stop,
    Vehicle,
    construct,
    input_errors,
    verify,
)
from pp_routecraft.domain.instance import VisitSchedule
from pp_routecraft.fixtures import tiny


def plan(jobs: tuple[int, ...] = (1, 2, 3), cost: int = 8) -> Plan:
    return Plan((Route(0, jobs),), (1, cost))


def test_hand_computed_asymmetric_tour() -> None:
    instance = tiny()
    report = verify(instance, plan())
    assert report.valid
    assert report.objective == (1, 8)  # 0->1->2->3->0: four arcs of 2.
    reverse = verify(instance, plan((3, 2, 1), 30))
    assert reverse.objective == (1, 30)  # 6 + 8 + 9 + 7, not the forward cost.
    assert not reverse.valid  # Return is beyond the vehicle's shift of 20.


@pytest.mark.parametrize(
    ("candidate", "message"),
    [
        (plan((1, 2), 8), "missing"),
        (plan((1, 2, 3, 1), 8), "duplicate mandatory"),
        (plan((1, 2, 9), 8), "unknown mandatory"),
        (plan(cost=9), "cached objective"),
        (Plan((Route(0, (1, 2, 3)), Route(0, ())), (1, 8)), "duplicate vehicle"),
        (Plan((Route(99, (1, 2, 3)),), (1, 8)), "unknown vehicle"),
        (replace(plan(), schema_version=2), "schema"),
        (Plan((Route(0, (1, 2, 3), (), 99),), (1, 8)), "cached return"),
        (Plan((Route(0, (1, 2, 3), (VisitSchedule(1, 0, 0, 0, 0),)),), (1, 8)), "cached schedule"),
    ],
)
def test_rejects_bad_plans(candidate: Plan, message: str) -> None:
    report = verify(tiny(), candidate)
    assert not report.valid
    assert any(message in error for error in report.errors)


def test_capacity_window_service_and_depot_return() -> None:
    instance = tiny()
    overflow = replace(instance, vehicles=(Vehicle(0, 2), Vehicle(1, 2)))
    assert "capacity overflow" in " ".join(verify(overflow, plan()).errors)
    window = replace(instance, stops=(replace(instance.stops[0], due=1),) + instance.stops[1:])
    assert "window violation" in " ".join(verify(window, plan()).errors)
    shift = replace(instance, vehicles=(Vehicle(0, 3, 0, 7), Vehicle(1, 3)))
    assert "return-to-depot" in " ".join(verify(shift, plan()).errors)
    service = replace(
        instance, stops=(replace(instance.stops[0], service=20),) + instance.stops[1:]
    )
    assert "shift violation" in " ".join(verify(service, plan()).errors)


def test_waiting_and_service_start_window() -> None:
    instance = RoutingInstance((Stop(1, 1, 10, 10, 3),), (Vehicle(0, 2, 0, 20),), ((0, 2), (4, 0)))
    candidate = Plan((Route(0, (1,)),), (1, 6))
    report = verify(instance, candidate)
    assert report.valid
    assert report.schedules[0][1] == (VisitSchedule(1, 2, 10, 13, 0),)
    assert report.schedules[0][2] == 17
    assert construct(instance) is not None


@pytest.mark.parametrize(
    "instance",
    [
        replace(tiny(), depot=1),
        replace(tiny(), stops=(Stop(2, 1),)),
        replace(tiny(), travel=((0,),)),
        replace(tiny(), travel=((1, 2, 5, 6),) + tiny().travel[1:]),
        replace(tiny(), travel=((0, -2, 5, 6),) + tiny().travel[1:]),
        replace(tiny(), stops=(Stop(1, 0), Stop(2, 1), Stop(3, 1))),
        replace(tiny(), stops=(Stop(1, 1, 4, 3), Stop(2, 1), Stop(3, 1))),
        replace(tiny(), vehicles=()),
        replace(tiny(), vehicles=(Vehicle(0, 2), Vehicle(0, 2))),
        replace(tiny(), vehicles=(Vehicle(0, 0),)),
        replace(tiny(), vehicles=(Vehicle(0, 2, 5, 2),)),
    ],
)
def test_input_rejections(instance: RoutingInstance) -> None:
    assert input_errors(instance)
    assert not verify(instance, plan()).valid


def test_noncanonical_sdk_customer_order_is_consistently_invalid() -> None:
    """A03 review repro: keyed verifier and positional scheduler must agree."""
    from pp_routecraft import SearchBudget, Status, exhaustive, solve

    instance = RoutingInstance(
        (Stop(2, 1, 5, 50, 3), Stop(1, 1, 0, 50, 0)),
        (Vehicle(1, 3, 0, 100),),
        ((0, 1, 1), (1, 0, 1), (1, 1, 0)),
    )
    assert "ordered" in " ".join(input_errors(instance))
    assert solve(instance, SearchBudget(0)).status == Status.INVALID_INPUT
    assert exhaustive(instance).status == Status.INVALID_INPUT
    assert not verify(instance, Plan((Route(1, (1, 2)),), (1, 3))).valid
    for regret in (False, True):
        with pytest.raises(ValueError, match="ordered"):
            construct(instance, regret=regret)
    canonical = replace(instance, stops=tuple(sorted(instance.stops, key=lambda s: s.id)))
    result = solve(canonical, SearchBudget(0))
    assert result.status == Status.FEASIBLE
    assert result.plan is not None and result.plan.objective == (1, 3)
    assert verify(canonical, result.plan).valid
    # Both orders have objective (1,3); completion time is not a tie breaker.
    assert result.plan.routes[0].return_time in (9, 10)
    assert next(v for v in result.plan.routes[0].schedule if v.stop_id == 2).departure == 8
