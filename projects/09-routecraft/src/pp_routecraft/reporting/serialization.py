"""Versioned JSON boundary. Unknown/mistyped structures fail before solving."""

import json
from dataclasses import asdict
from math import isfinite
from pathlib import Path

from pp_routecraft.domain.instance import (
    LoadedJob,
    Plan,
    Route,
    RoutingInstance,
    Stop,
    Vehicle,
    VehicleState,
    VisitSchedule,
)


def _dict(value: object, allowed: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError("expected JSON object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"unknown JSON fields: {', '.join(sorted(unknown))}")
    return {str(k): v for k, v in value.items()}


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("expected JSON array")
    return list(value)


def _int(value: object) -> int:
    if type(value) is not int:
        raise ValueError("expected integer units")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected string")
    return value


def _float(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("expected coordinate number")
    try:
        coordinate = float(value)
    except OverflowError as error:
        raise ValueError("coordinate must be a finite representable number") from error
    if not isfinite(coordinate):
        raise ValueError("coordinate must be a finite representable number")
    return coordinate


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("expected boolean")
    return value


def instance_dict(instance: RoutingInstance) -> dict[str, object]:
    return {"schema_version": 1, **asdict(instance)}


def instance_from_dict(value: object) -> RoutingInstance:
    data = _dict(
        value,
        ("schema_version", "stops", "vehicles", "travel", "depot", "matrix_version", "states"),
    )
    if _int(data.get("schema_version")) != 1:
        raise ValueError("unsupported instance schema")
    stops = []
    for item in _list(data.get("stops")):
        s = _dict(item, ("id", "demand", "ready", "due", "service", "x", "y"))
        stops.append(
            Stop(
                _int(s.get("id")),
                _int(s.get("demand")),
                _int(s.get("ready")),
                _int(s.get("due")),
                _int(s.get("service")),
                _float(s.get("x", 0)),
                _float(s.get("y", 0)),
            )
        )
    vehicles = []
    for item in _list(data.get("vehicles")):
        v = _dict(item, ("id", "capacity", "start", "end"))
        vehicles.append(
            Vehicle(
                _int(v.get("id")), _int(v.get("capacity")), _int(v.get("start")), _int(v.get("end"))
            )
        )
    states = []
    for item in _list(data.get("states", [])):
        s = _dict(
            item,
            ("vehicle_id", "started", "executed", "node", "time", "onboard", "loaded", "boundary"),
        )
        jobs = []
        for entry in _list(s.get("loaded")):
            j = _dict(entry, ("stop_id", "quantity"))
            jobs.append(LoadedJob(_int(j.get("stop_id")), _int(j.get("quantity"))))
        states.append(
            VehicleState(
                _int(s.get("vehicle_id")),
                _bool(s.get("started")),
                tuple(_int(j) for j in _list(s.get("executed"))),
                _int(s.get("node")),
                _int(s.get("time")),
                _int(s.get("onboard")),
                tuple(jobs),
                _str(s.get("boundary")),
            )
        )
    return RoutingInstance(
        tuple(stops),
        tuple(vehicles),
        tuple(tuple(_int(v) for v in _list(row)) for row in _list(data.get("travel"))),
        _int(data.get("depot", 0)),
        _str(data.get("matrix_version", "synthetic-v1")),
        tuple(states),
    )


def plan_from_dict(value: object) -> Plan:
    data = _dict(value, ("routes", "objective", "schema_version"))
    if _int(data.get("schema_version")) != 1:
        raise ValueError("unsupported plan schema")
    routes = []
    for item in _list(data.get("routes")):
        r = _dict(item, ("vehicle_id", "stops", "schedule", "return_time"))
        visits = []
        for entry in _list(r.get("schedule", [])):
            s = _dict(entry, ("stop_id", "arrival", "service_start", "departure", "onboard_after"))
            visits.append(
                VisitSchedule(
                    _int(s.get("stop_id")),
                    _int(s.get("arrival")),
                    _int(s.get("service_start")),
                    _int(s.get("departure")),
                    _int(s.get("onboard_after")),
                )
            )
        return_time = r.get("return_time")
        routes.append(
            Route(
                _int(r.get("vehicle_id")),
                tuple(_int(j) for j in _list(r.get("stops"))),
                tuple(visits),
                None if return_time is None else _int(return_time),
            )
        )
    objective = _list(data.get("objective"))
    if len(objective) != 2:
        raise ValueError("lexicographic objective needs two values")
    return Plan(
        tuple(routes), (_int(objective[0]), _int(objective[1])), _int(data.get("schema_version"))
    )


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    data: dict[str, object] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate JSON object key: {key}")
        data[key] = value
    return data


def read_instance(path: Path) -> RoutingInstance:
    return instance_from_dict(
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    )


def read_plan(path: Path) -> Plan:
    return plan_from_dict(
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    )
