"""Independent verification: no construction, move, or search imports.

Every arc, waiting period, remaining load and return is recomputed here. Optional
cached schedules and the mandatory cached objective are treated as assertions.
"""

from collections import Counter
from dataclasses import dataclass
from math import isfinite

from pp_routecraft.domain.instance import Plan, RoutingInstance, VisitSchedule


@dataclass(frozen=True)
class Verification:
    valid: bool
    errors: tuple[str, ...]
    objective: tuple[int, int]
    schedules: tuple[tuple[int, tuple[VisitSchedule, ...], int], ...]


def input_errors(instance: RoutingInstance) -> tuple[str, ...]:
    errors: list[str] = []
    ids = [s.id for s in instance.stops]
    vids = [v.id for v in instance.vehicles]
    if instance.depot != 0:
        errors.append("only depot node zero is supported")
    if ids != list(range(1, len(ids) + 1)):
        errors.append("customer records must be ordered by unique contiguous matrix nodes 1..n")
    if len(set(vids)) != len(vids) or not vids:
        errors.append("vehicles must have unique IDs and at least one vehicle")
    n = len(ids) + 1
    if len(instance.travel) != n or any(len(row) != n for row in instance.travel):
        errors.append("travel matrix dimensions must be n+1 squared")
    else:
        for i, row in enumerate(instance.travel):
            if any(type(value) is not int or value < 0 for value in row):
                errors.append("travel times must be nonnegative integers")
            if row[i] != 0:
                errors.append("matrix diagonal must be zero")
    for stop in instance.stops:
        values = (stop.id, stop.demand, stop.ready, stop.due, stop.service)
        if any(type(value) is not int or value < 0 for value in values):
            errors.append(f"stop {stop.id}: nonnegative integer units required")
        elif stop.ready > stop.due or stop.demand == 0:
            errors.append(f"stop {stop.id}: invalid window or demand")
        if not isfinite(stop.x) or not isfinite(stop.y):
            errors.append(f"stop {stop.id}: coordinates must be finite")
    for vehicle in instance.vehicles:
        vehicle_values = (vehicle.id, vehicle.capacity, vehicle.start, vehicle.end)
        if any(type(value) is not int or value < 0 for value in vehicle_values):
            errors.append(f"vehicle {vehicle.id}: nonnegative integer units required")
        elif vehicle.capacity == 0 or vehicle.start > vehicle.end:
            errors.append(f"vehicle {vehicle.id}: invalid capacity or shift")
    state_ids = [s.vehicle_id for s in instance.states]
    if instance.states and (sorted(state_ids) != sorted(vids)):
        errors.append("replanning requires exactly one state per vehicle")
    executed_all: list[int] = []
    loaded_all: list[int] = []
    by_id = {s.id: s for s in instance.stops}
    vehicle_map = {v.id: v for v in instance.vehicles}
    for state in instance.states:
        state_vehicle = vehicle_map.get(state.vehicle_id)
        executed_all.extend(state.executed)
        loaded_all.extend(job.stop_id for job in state.loaded)
        if state.boundary not in ("departure", "service_complete"):
            errors.append("unsupported mid-edge/in-service snapshot")
        if type(state.time) is not int or type(state.onboard) is not int:
            errors.append("snapshot units must be integers")
            continue
        if state.node != (state.executed[-1] if state.executed else 0):
            errors.append("snapshot node must match completed prefix boundary")
        if not state.started and (state.executed or state.onboard or state.loaded):
            errors.append("unstarted vehicle cannot already carry cargo or completed jobs")
        if state_vehicle and not (state_vehicle.start <= state.time <= state_vehicle.end):
            errors.append("snapshot outside vehicle shift")
        quantities = [job.quantity for job in state.loaded]
        if any(type(q) is not int or q <= 0 for q in quantities):
            errors.append("manifest quantities must be positive integers")
            continue
        if state.onboard != sum(quantities) or state.onboard < 0:
            errors.append("onboard quantity disagrees with cargo manifest")
        if state_vehicle and state.onboard > state_vehicle.capacity:
            errors.append("onboard exceeds vehicle capacity")
        for job in state.loaded:
            loaded_stop = by_id.get(job.stop_id)
            if loaded_stop is None or loaded_stop.demand != job.quantity:
                errors.append("loaded job missing or quantity disagrees with demand")
        if any(node not in by_id for node in state.executed):
            errors.append("unknown executed stop")
    if len(set(executed_all)) != len(executed_all):
        errors.append("duplicate executed stops")
    if len(set(loaded_all)) != len(loaded_all) or set(loaded_all) & set(executed_all):
        errors.append("duplicate loaded jobs or delivered job still onboard")
    return tuple(errors)


def verify(instance: RoutingInstance, plan: Plan) -> Verification:
    errors = list(input_errors(instance))
    if errors:
        return Verification(False, tuple(errors), (0, 0), ())
    if any(type(value) is not int for value in plan.objective):
        errors.append("objective must use integer units")
    if plan.schema_version != 1:
        errors.append("unsupported plan schema version")
    stops = {s.id: s for s in instance.stops}
    vehicles = {v.id: v for v in instance.vehicles}
    states = {s.vehicle_id: s for s in instance.states}
    counts = Counter(node for route in plan.routes for node in route.stops)
    if set(counts) != set(stops):
        errors.append("missing or unknown mandatory stop")
    if any(count != 1 for count in counts.values()):
        errors.append("duplicate mandatory stop")
    if len({r.vehicle_id for r in plan.routes}) != len(plan.routes):
        errors.append("duplicate vehicle route")
    if any(r.vehicle_id not in vehicles for r in plan.routes):
        errors.append("unknown vehicle")
    if errors:
        return Verification(False, tuple(errors), (0, 0), ())
    used = 0
    travel = 0
    schedules: list[tuple[int, tuple[VisitSchedule, ...], int]] = []
    for route in plan.routes:
        vehicle = vehicles[route.vehicle_id]
        state = states.get(vehicle.id)
        prefix = state.executed if state else ()
        if route.stops[: len(prefix)] != prefix:
            errors.append("changed executed route prefix")
        suffix = route.stops[len(prefix) :]
        if state and state.started:
            if set(suffix) != {job.stop_id for job in state.loaded}:
                errors.append("started vehicle must deliver exactly its onboard jobs")
        elif states:
            assigned = {job.stop_id for s in states.values() if s.started for job in s.loaded}
            if assigned & set(suffix):
                errors.append("loaded jobs cannot transfer vehicles")
        used += bool(route.stops)
        # Replay executed history independently, then use actual boundary state.
        clock = vehicle.start
        node = 0
        remaining = sum(stops[j].demand for j in route.stops)
        if state and state.started:
            remaining = state.onboard + sum(stops[j].demand for j in prefix)
        if remaining > vehicle.capacity:
            errors.append(f"vehicle {vehicle.id}: capacity overflow")
        visits: list[VisitSchedule] = []
        for index, job_id in enumerate(route.stops):
            if index == len(prefix) and state:
                if state.time < clock:
                    errors.append("actual boundary time precedes executed service completion")
                clock, node = state.time, state.node
                if state.started:
                    remaining = state.onboard
            stop = stops[job_id]
            arc = instance.travel[node][job_id]
            arrival = clock + arc
            start = max(arrival, stop.ready)
            clock = start + stop.service
            remaining -= stop.demand
            travel += arc
            if start > stop.due:
                errors.append(f"stop {job_id}: service-start window violation")
            if clock > vehicle.end:
                errors.append(f"vehicle {vehicle.id}: shift violation")
            if remaining < 0:
                errors.append(f"vehicle {vehicle.id}: invented cargo")
            visits.append(VisitSchedule(job_id, arrival, start, clock, remaining))
            node = job_id
        if state and len(prefix) == len(route.stops):
            if state.time < clock:
                errors.append("actual boundary time precedes executed service completion")
            clock, node = state.time, state.node
        if route.stops:
            travel += instance.travel[node][0]
            clock += instance.travel[node][0]
        if clock > vehicle.end:
            errors.append(f"vehicle {vehicle.id}: return-to-depot shift violation")
        if route.schedule and route.schedule != tuple(visits):
            errors.append(f"vehicle {vehicle.id}: inconsistent cached schedule")
        if route.return_time is not None and route.return_time != clock:
            errors.append(f"vehicle {vehicle.id}: inconsistent cached return")
        schedules.append((vehicle.id, tuple(visits), clock))
    for state in states.values():
        if (state.executed or state.loaded) and state.vehicle_id not in {
            r.vehicle_id for r in plan.routes
        }:
            errors.append("missing started vehicle route")
    objective = (used, travel)
    if plan.objective != objective:
        errors.append("inconsistent cached objective")
    return Verification(not errors, tuple(errors), objective, tuple(schedules))
