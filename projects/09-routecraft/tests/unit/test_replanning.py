"""RC-07: real cargo stays aboard its vehicle; spare capacity cannot invent it."""

from dataclasses import replace

import pytest

from pp_routecraft import (
    LoadedJob,
    Plan,
    Route,
    SearchBudget,
    VehicleState,
    construct,
    input_errors,
    prepare_replan,
    solve,
    verify,
)
from pp_routecraft.fixtures import new_request, tiny


def prepared():
    instance = replace(tiny(), vehicles=tuple(replace(v, end=100) for v in tiny().vehicles))
    plan = construct(instance, regret=False)
    assert plan is not None
    expanded = new_request(instance, plan)
    return instance, plan, expanded


def test_replan_actual_node_time_and_manifest() -> None:
    previous, plan, updated = prepared()
    states = tuple(replace(s, time=s.time + 4) if s.started else s for s in updated.states)
    replanning = prepare_replan(previous, plan, replace(updated, states=()), states)
    result = solve(replanning, SearchBudget(80))
    assert result.plan is not None
    assert verify(replanning, result.plan).valid
    active = next(s for s in replanning.states if s.started)
    route = next(r for r in result.plan.routes if r.vehicle_id == active.vehicle_id)
    assert route.stops[:1] == (1,)
    assert set(route.stops[1:]) == {2, 3}
    assert 4 not in route.stops
    assert route.schedule[1].arrival == active.time + replanning.travel[active.node][route.stops[1]]
    assert route.schedule[1].onboard_after == 1
    assert any(4 in r.stops for r in result.plan.routes if r.vehicle_id != active.vehicle_id)


@pytest.mark.parametrize("boundary", ["mid_edge", "in_service", "arrival"])
def test_reject_nonboundary_snapshots(boundary: str) -> None:
    old, plan, updated = prepared()
    states = (replace(updated.states[0], boundary=boundary),) + updated.states[1:]
    with pytest.raises(ValueError, match="mid-edge/in-service"):
        prepare_replan(old, plan, updated, states)


def test_reject_executed_definition_and_matrix_changes() -> None:
    old, plan, updated = prepared()
    changed = replace(updated, stops=(replace(updated.stops[0], service=99),) + updated.stops[1:])
    with pytest.raises(ValueError, match="executed stop definition"):
        prepare_replan(old, plan, changed, updated.states)
    matrix = list(updated.travel)
    matrix[0] = (0, 99) + matrix[0][2:]
    with pytest.raises(ValueError, match="matrix costs"):
        prepare_replan(old, plan, replace(updated, travel=tuple(matrix)), updated.states)
    with pytest.raises(ValueError, match="matrix version"):
        prepare_replan(old, plan, replace(updated, matrix_version="v2"), updated.states)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("node", "node must match"),
        ("time", "precedes executed"),
        ("overload", "onboard"),
        ("quantity", "quantity"),
        ("missing", "original vehicle"),
        ("duplicate", "duplicate loaded"),
        ("completed_loaded", "delivered job"),
        ("unstarted_cargo", "unstarted vehicle"),
        ("shift", "outside vehicle shift"),
        ("prefix", "changed executed"),
        ("unknown", "unknown executed"),
    ],
)
def test_manifest_and_snapshot_failures(mutation: str, message: str) -> None:
    old, plan, updated = prepared()
    active, idle = updated.states
    if mutation == "node":
        active = replace(active, node=0)
    elif mutation == "time":
        active = replace(active, time=1)
    elif mutation == "overload":
        active = replace(active, onboard=4)
    elif mutation == "quantity":
        active = replace(active, loaded=(LoadedJob(2, 2), LoadedJob(3, 1)), onboard=3)
    elif mutation == "missing":
        active = replace(active, loaded=(LoadedJob(2, 1),), onboard=1)
    elif mutation == "duplicate":
        active = replace(active, loaded=(LoadedJob(2, 1), LoadedJob(2, 1)), onboard=2)
    elif mutation == "completed_loaded":
        active = replace(active, loaded=(LoadedJob(1, 1), LoadedJob(2, 1)), onboard=2)
    elif mutation == "unstarted_cargo":
        idle = replace(idle, onboard=1, loaded=(LoadedJob(4, 1),))
    elif mutation == "shift":
        active = replace(active, time=100000)
    elif mutation == "prefix":
        active = replace(active, executed=(3,), node=3, loaded=(LoadedJob(1, 1), LoadedJob(2, 1)))
    elif mutation == "unknown":
        active = replace(active, executed=(99,), node=99)
    with pytest.raises(ValueError, match=message):
        prepare_replan(old, plan, updated, (active, idle))


def test_transfer_loaded_job_and_new_unloaded_assignment_rejected() -> None:
    old, plan, updated = prepared()
    active, idle = updated.states
    transferred = (
        replace(active, loaded=(LoadedJob(3, 1),), onboard=1),
        replace(idle, started=True, loaded=(LoadedJob(2, 1),), onboard=1),
    )
    with pytest.raises(ValueError, match="original vehicle"):
        prepare_replan(old, plan, updated, transferred)
    illegal = Plan((Route(0, (1, 2, 3, 4)), Route(1, ())), (1, 0))
    report = verify(updated, illegal)
    assert not report.valid
    assert "exactly its onboard jobs" in " ".join(report.errors)
    transferred_plan = Plan((Route(0, (1, 3)), Route(1, (2, 4))), (2, 0))
    assert "cannot transfer" in " ".join(verify(updated, transferred_plan).errors)


def test_missing_states_vehicles_customers_and_invalid_previous() -> None:
    old, plan, updated = prepared()
    with pytest.raises(ValueError, match="exactly one state"):
        prepare_replan(old, plan, updated, updated.states[:1])
    with pytest.raises(ValueError, match="vehicles"):
        prepare_replan(old, plan, replace(updated, vehicles=updated.vehicles[:1]), updated.states)
    with pytest.raises(ValueError, match="disappear"):
        prepare_replan(old, plan, replace(updated, stops=updated.stops[:2]), updated.states)
    with pytest.raises(ValueError, match="previous plan"):
        prepare_replan(old, replace(plan, objective=(1, 999)), updated, updated.states)


def test_completed_route_can_return_from_actual_boundary() -> None:
    old, plan, updated = prepared()
    active = VehicleState(0, True, (1, 2, 3), 3, 7, 0, ())
    idle = updated.states[1]
    replanning = prepare_replan(old, plan, updated, (active, idle))
    result = solve(replanning, SearchBudget(20))
    assert result.plan is not None
    assert verify(replanning, result.plan).valid
    route = next(r for r in result.plan.routes if r.vehicle_id == 0)
    assert route.return_time == 9  # actual t=7 + directed return 3->0=2
    assert route.stops == (1, 2, 3)


def test_negative_manifest_and_duplicate_executed() -> None:
    _, _, updated = prepared()
    active, idle = updated.states
    bad = replace(active, loaded=(LoadedJob(2, -1),), onboard=-1)
    assert "positive integers" in " ".join(input_errors(replace(updated, states=(bad, idle))))
    duplicate = replace(idle, started=True, executed=(1,), node=1, time=2)
    assert "duplicate executed" in " ".join(
        input_errors(replace(updated, states=(active, duplicate)))
    )


def test_direct_state_cannot_move_boundary_before_history() -> None:
    _, _, updated = prepared()
    active, idle = updated.states
    invalid = replace(updated, states=(replace(active, time=1), idle))
    # Even a caller bypassing history preparation cannot publish time travel.
    candidate = Plan((Route(0, (1, 2, 3)), Route(1, (4,))), (2, 31))
    assert "precedes executed" in " ".join(verify(invalid, candidate).errors)
    assert solve(invalid, SearchBudget(0)).plan is None


def test_repeated_replanning_cannot_reset_started_or_executed_history() -> None:
    _, _, first = prepared()
    first_result = solve(first, SearchBudget(10))
    assert first_result.plan is not None
    active, idle = first.states
    reset = replace(active, started=False, executed=(), node=0, onboard=0, loaded=())
    with pytest.raises(ValueError, match="become unstarted"):
        prepare_replan(first, first_result.plan, first, (reset, idle))
    shrink = replace(
        active,
        executed=(),
        node=0,
        onboard=3,
        loaded=(LoadedJob(1, 1), LoadedJob(2, 1), LoadedJob(3, 1)),
    )
    with pytest.raises(ValueError, match="cannot shrink"):
        prepare_replan(first, first_result.plan, first, (shrink, idle))
    delayed = replace(active, time=3)
    delayed_first = replace(first, states=(delayed, idle))
    delayed_result = solve(delayed_first, SearchBudget(0))
    assert delayed_result.plan is not None
    with pytest.raises(ValueError, match="move backward"):
        prepare_replan(delayed_first, delayed_result.plan, delayed_first, (active, idle))
    assert prepare_replan(first, first_result.plan, first, first.states).states == first.states
