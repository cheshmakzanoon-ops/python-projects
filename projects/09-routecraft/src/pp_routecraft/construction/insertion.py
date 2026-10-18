"""Authored directed feasible insertion with deterministic regret tie breaking."""

import random
from dataclasses import dataclass

from pp_routecraft.domain.instance import Plan, Route, RoutingInstance, VisitSchedule
from pp_routecraft.validation.verifier import input_errors


@dataclass(frozen=True)
class Candidate:
    delta: tuple[int, int]
    vehicle_index: int
    position: int
    route: Route
    travel: int


def evaluate_route(
    instance: RoutingInstance, vehicle_index: int, jobs: tuple[int, ...]
) -> tuple[Route, int] | None:
    """Optimizer's scheduler. The independent verifier deliberately duplicates this logic."""
    vehicle = instance.vehicles[vehicle_index]
    state = next((s for s in instance.states if s.vehicle_id == vehicle.id), None)
    prefix = state.executed if state else ()
    if jobs[: len(prefix)] != prefix:
        return None
    suffix = jobs[len(prefix) :]
    if state and state.started:
        allowed = {job.stop_id for job in state.loaded}
        if not set(suffix) <= allowed:
            return None
    elif instance.states:
        occupied = {job.stop_id for s in instance.states if s.started for job in s.loaded}
        if occupied & set(suffix):
            return None
    remaining = sum(instance.stops[j - 1].demand for j in jobs)
    if state and state.started:
        # A partial repair still carries *all* manifest cargo until delivered.
        remaining = state.onboard + sum(instance.stops[j - 1].demand for j in prefix)
    if remaining > vehicle.capacity:
        return None
    clock, node, cost = vehicle.start, 0, 0
    visits: list[VisitSchedule] = []
    for index, job in enumerate(jobs):
        if state and index == len(prefix):
            if state.time < clock:
                return None
            clock, node = state.time, state.node
            if state.started:
                remaining = state.onboard
        stop = instance.stops[job - 1]
        arc = instance.travel[node][job]
        arrival = clock + arc
        begin = max(arrival, stop.ready)
        clock = begin + stop.service
        remaining -= stop.demand
        if begin > stop.due or clock > vehicle.end or remaining < 0:
            return None
        visits.append(VisitSchedule(job, arrival, begin, clock, remaining))
        cost += arc
        node = job
    if state and len(prefix) == len(jobs):
        if state.time < clock:
            return None
        clock, node = state.time, state.node
    if jobs:
        cost += instance.travel[node][0]
        clock += instance.travel[node][0]
    if clock > vehicle.end:
        return None
    return Route(vehicle.id, jobs, tuple(visits), clock), cost


def empty_routes(instance: RoutingInstance) -> list[tuple[int, ...]]:
    states = {s.vehicle_id: s for s in instance.states}
    return [states[v.id].executed if v.id in states else () for v in instance.vehicles]


def options(instance: RoutingInstance, routes: list[tuple[int, ...]], job: int) -> list[Candidate]:
    choices: list[Candidate] = []
    state_map = {s.vehicle_id: s for s in instance.states}
    for index, jobs in enumerate(routes):
        vehicle = instance.vehicles[index]
        state = state_map.get(vehicle.id)
        if state and state.started and job not in {j.stop_id for j in state.loaded}:
            continue
        if not state or not state.started:
            demand = sum(instance.stops[j - 1].demand for j in jobs)
            if demand + instance.stops[job - 1].demand > vehicle.capacity:
                continue
        original = evaluate_route(instance, index, jobs)
        if original is None:
            continue
        prefix_length = len(state.executed) if state else 0
        for position in range(prefix_length, len(jobs) + 1):
            inserted = jobs[:position] + (job,) + jobs[position:]
            result = evaluate_route(instance, index, inserted)
            if result is None:
                continue
            route, cost = result
            delta = (int(not jobs), cost - original[1])
            choices.append(Candidate(delta, index, position, route, cost))
    return sorted(choices, key=lambda c: (c.delta, c.vehicle_index, c.position))


def repair(
    instance: RoutingInstance,
    routes: list[tuple[int, ...]],
    pending: list[int],
    *,
    regret: bool,
    shuffle_seed: int | None = None,
) -> list[tuple[int, ...]] | None:
    routes = list(routes)
    remaining = sorted(pending, key=lambda j: (instance.stops[j - 1].due, j))
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(remaining)
    while remaining:
        if regret:
            # Bounded lookahead keeps large construction practical. All jobs still
            # receive a real feasibility evaluation when selected.
            candidates: list[tuple[tuple[int, int, int, int], int, Candidate]] = []
            for job in remaining[:8]:
                choices = options(instance, routes, job)
                if not choices:
                    return None
                best = choices[0]
                second = choices[1] if len(choices) > 1 else None
                scarcity = 1 if second is None else 0
                vehicle_regret = (second.delta[0] - best.delta[0]) if second else 1
                travel_regret = (second.delta[1] - best.delta[1]) if second else 0
                key = (scarcity, vehicle_regret, travel_regret, -job)
                candidates.append((key, job, best))
            _, job, best = max(candidates, key=lambda row: row[0])
        else:
            job = remaining[0]
            choices = options(instance, routes, job)
            if not choices:
                return None
            best = choices[0]
        routes[best.vehicle_index] = best.route.stops
        remaining.remove(job)
    return routes


def make_plan(instance: RoutingInstance, routes: list[tuple[int, ...]]) -> Plan | None:
    result: list[Route] = []
    cost = 0
    for index, jobs in enumerate(routes):
        evaluated = evaluate_route(instance, index, jobs)
        if evaluated is None:
            return None
        route, travel = evaluated
        result.append(route)
        cost += travel
    return Plan(tuple(result), (sum(bool(route.stops) for route in result), cost))


def construct(
    instance: RoutingInstance, *, regret: bool = True, seed: int | None = None
) -> Plan | None:
    errors = input_errors(instance)
    if errors:
        raise ValueError("; ".join(errors))
    routes = empty_routes(instance)
    completed = {j for jobs in routes for j in jobs}
    repaired = repair(
        instance,
        routes,
        [s.id for s in instance.stops if s.id not in completed],
        regret=regret,
        shuffle_seed=seed,
    )
    return make_plan(instance, repaired) if repaired is not None else None
