"""Boundary-only rolling planning with manifest and historical immutability checks."""

from dataclasses import replace

from pp_routecraft.domain.instance import Plan, RoutingInstance, VehicleState
from pp_routecraft.validation.verifier import input_errors, verify


def prepare_replan(
    previous: RoutingInstance,
    previous_plan: Plan,
    expanded: RoutingInstance,
    states: tuple[VehicleState, ...],
) -> RoutingInstance:
    report = verify(previous, previous_plan)
    if not report.valid:
        raise ValueError(f"previous plan is invalid: {report.errors}")
    if expanded.vehicles != previous.vehicles or expanded.depot != previous.depot:
        raise ValueError("vehicles and depot cannot change in baseline replanning")
    if len(expanded.stops) < len(previous.stops):
        raise ValueError("existing customers cannot disappear")
    for i, row in enumerate(previous.travel):
        for j, value in enumerate(row):
            if (
                i >= len(expanded.travel)
                or j >= len(expanded.travel[i])
                or expanded.travel[i][j] != value
            ):
                raise ValueError(
                    "existing-node matrix costs cannot change; traffic updates unsupported"
                )
    if expanded.matrix_version != previous.matrix_version:
        raise ValueError("matrix version changes require a separate traffic-update implementation")
    candidate = replace(expanded, states=states)
    errors = input_errors(candidate)
    if errors:
        raise ValueError("; ".join(errors))
    old_routes = {r.vehicle_id: r for r in previous_plan.routes}
    old_stops = {s.id: s for s in previous.stops}
    new_stops = {s.id: s for s in expanded.stops}
    old_schedules = {vid: visits for vid, visits, _ in report.schedules}
    prior_states = {state.vehicle_id: state for state in previous.states}
    for state in states:
        prior = prior_states.get(state.vehicle_id)
        if prior is not None:
            if prior.started and not state.started:
                raise ValueError("an already started vehicle cannot become unstarted")
            if state.executed[: len(prior.executed)] != prior.executed:
                raise ValueError("an already executed prefix cannot shrink or change")
            if state.time < prior.time:
                raise ValueError("actual snapshot time cannot move backward")
        route = old_routes.get(state.vehicle_id)
        jobs = route.stops if route else ()
        if jobs[: len(state.executed)] != state.executed:
            raise ValueError("changed executed stops or order")
        for job in state.executed:
            if old_stops.get(job) != new_stops[job]:
                raise ValueError("changed executed stop definition")
        if state.started:
            remaining = jobs[len(state.executed) :]
            if {job.stop_id for job in state.loaded} != set(remaining):
                raise ValueError("loaded jobs must remain on their original vehicle")
            for loaded_job in state.loaded:
                if old_stops[loaded_job.stop_id].demand != loaded_job.quantity:
                    raise ValueError("manifest quantity differs from original load")
        if state.executed:
            departure = old_schedules[state.vehicle_id][len(state.executed) - 1].departure
            if state.time < departure:
                raise ValueError("actual boundary time precedes executed service completion")
        elif state.started and state.node != 0:
            raise ValueError("started vehicle without executed prefix must be at depot")
    return candidate
