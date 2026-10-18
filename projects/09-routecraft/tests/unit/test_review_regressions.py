"""Regressions for historical-state, SDK boundary, and incumbent handling defects."""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from pp_routecraft import (
    Plan,
    Route,
    RoutingInstance,
    SearchBudget,
    Status,
    Stop,
    Vehicle,
    construct,
    input_errors,
    prepare_replan,
    solve,
    verify,
)
from pp_routecraft.construction.insertion import make_plan
from pp_routecraft.fixtures import new_request, tiny
from pp_routecraft.reporting.serialization import instance_dict, instance_from_dict


@pytest.mark.parametrize("repeated", [False, True])
def test_replanning_cannot_omit_all_vehicle_states(repeated: bool) -> None:
    previous = tiny()
    previous = replace(previous, vehicles=tuple(replace(v, end=100) for v in previous.vehicles))
    plan = construct(previous)
    assert plan is not None
    expanded = new_request(previous, plan)
    if repeated:
        previous = expanded
        plan = construct(previous)
        assert plan is not None
    with pytest.raises(ValueError, match="exactly one state"):
        prepare_replan(previous, plan, expanded, ())


@pytest.mark.parametrize(
    "field",
    [
        "schema_bool",
        "schema_float",
        "vehicle_bool",
        "vehicle_float",
        "stop_bool",
        "stop_float",
        "schedule",
        "return",
    ],
)
def test_verifier_rejects_noninteger_aliases_in_sdk_plans(field: str) -> None:
    instance = tiny()
    plan = construct(instance)
    assert plan is not None
    route = plan.routes[0]
    if field.startswith("schema"):
        plan = replace(plan, schema_version=True if field == "schema_bool" else 1.0)  # type: ignore[arg-type]
    elif field.startswith("vehicle"):
        route = replace(route, vehicle_id=False if field == "vehicle_bool" else 0.0)  # type: ignore[arg-type]
    elif field.startswith("stop"):
        route = replace(route, stops=(True if field == "stop_bool" else 1.0,) + route.stops[1:])  # type: ignore[arg-type]
    elif field == "schedule":
        visit = replace(route.schedule[0], arrival=float(route.schedule[0].arrival))
        route = replace(route, schedule=(visit,) + route.schedule[1:])
    else:
        route = replace(route, return_time=float(route.return_time))  # type: ignore[arg-type]
    if not field.startswith("schema"):
        plan = replace(plan, routes=(route,) + plan.routes[1:])
    report = verify(instance, plan)
    assert not report.valid


@pytest.mark.parametrize("field", ["depot", "vehicle", "started", "node", "executed", "loaded"])
def test_sdk_snapshot_identity_and_boolean_types_are_validated(field: str) -> None:
    instance = tiny()
    plan = construct(instance)
    assert plan is not None
    instance = new_request(instance, plan)
    active, idle = instance.states
    if field == "depot":
        instance = replace(instance, depot=False)
    elif field == "vehicle":
        active = replace(active, vehicle_id=0.0)  # type: ignore[arg-type]
    elif field == "started":
        active = replace(active, started=1)  # type: ignore[arg-type]
    elif field == "node":
        active = replace(active, node=1.0)  # type: ignore[arg-type]
    elif field == "executed":
        active = replace(active, executed=(1.0,))  # type: ignore[arg-type]
    else:
        active = replace(
            active, loaded=(replace(active.loaded[0], stop_id=2.0),) + active.loaded[1:]
        )  # type: ignore[arg-type]
    instance = replace(instance, states=(active, idle))
    assert input_errors(instance)
    assert solve(instance, SearchBudget(0)).status == Status.INVALID_INPUT


@pytest.mark.parametrize(
    "coordinate",
    [10**400, float("nan"), True, "invalid"],
    ids=["overflow", "nan", "bool", "string"],
)
def test_sdk_rejects_coordinates_that_cannot_be_rendered(coordinate: object) -> None:
    instance = tiny()
    first = replace(instance.stops[0], x=coordinate)  # type: ignore[arg-type]
    instance = replace(instance, stops=(first,) + instance.stops[1:])
    assert input_errors(instance)
    assert solve(instance).status == Status.INVALID_INPUT


def test_json_rejects_unrepresentable_coordinate_without_overflow() -> None:
    payload = json.loads(json.dumps(instance_dict(tiny())))
    payload["stops"][0]["x"] = 10**400
    with pytest.raises(ValueError, match="coordinate"):
        instance_from_dict(payload)


@pytest.mark.parametrize(
    "seconds", [True, "invalid", 10**400, float("nan")], ids=["bool", "string", "overflow", "nan"]
)
def test_invalid_numeric_budget_returns_status(seconds: object) -> None:
    result = solve(tiny(), SearchBudget(1, seconds))  # type: ignore[arg-type]
    assert result.status == Status.INVALID_INPUT


def test_large_integer_costs_do_not_overflow_annealing() -> None:
    factor = 10**400
    instance = tiny()
    instance = replace(
        instance,
        travel=tuple(tuple(value * factor for value in row) for row in instance.travel),
        stops=tuple(replace(stop, due=100 * factor) for stop in instance.stops),
        vehicles=tuple(replace(vehicle, end=100 * factor) for vehicle in instance.vehicles),
    )
    incumbent = make_plan(instance, [(1, 2, 3), ()])
    worse = make_plan(instance, [(3, 2, 1), ()])
    assert incumbent is not None and worse is not None
    with (
        patch("pp_routecraft.search.solver.reverse_segment", return_value=worse),
        patch("random.Random.choices", return_value=[2]),
    ):
        result = solve(instance, SearchBudget(1), initial=incumbent)
    assert result.plan == incumbent
    assert verify(instance, result.plan).valid


@pytest.mark.parametrize("reordered", [False, True])
def test_initial_plan_representation_does_not_hide_available_vehicles(reordered: bool) -> None:
    instance = RoutingInstance(
        (Stop(1, 1), Stop(2, 1)),
        (Vehicle(0, 1), Vehicle(1, 1), Vehicle(2, 2)),
        ((0, 1, 1), (1, 0, 1), (1, 1, 0)),
    )
    routes = (Route(0, (1,)), Route(1, (2,)))
    initial = Plan(tuple(reversed(routes)) if reordered else routes, (2, 4))
    assert verify(instance, initial).valid
    result = solve(instance, SearchBudget(100), seed=0, initial=initial)
    assert result.plan is not None
    assert result.plan.objective == (1, 3)
    assert tuple(route.vehicle_id for route in result.plan.routes) == (0, 1, 2)
    assert verify(instance, result.plan).valid
