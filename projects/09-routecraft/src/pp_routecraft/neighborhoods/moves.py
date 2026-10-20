"""Original directed neighborhoods; never apply a symmetric two-opt delta."""

import random

from pp_routecraft.construction.insertion import make_plan, repair
from pp_routecraft.domain.instance import Plan, RoutingInstance


def movable(instance: RoutingInstance, plan: Plan) -> list[tuple[int, int]]:
    states = {s.vehicle_id: s for s in instance.states}
    return [
        (i, j)
        for i, route in enumerate(plan.routes)
        for j in range(
            len(states[route.vehicle_id].executed) if route.vehicle_id in states else 0,
            len(route.stops),
        )
    ]


def relocate(instance: RoutingInstance, plan: Plan, rng: random.Random) -> Plan | None:
    choices = movable(instance, plan)
    if not choices:
        return None
    source, position = rng.choice(choices)
    routes = [r.stops for r in plan.routes]
    job = routes[source][position]
    routes[source] = routes[source][:position] + routes[source][position + 1 :]
    destination = rng.randrange(len(routes))
    state = next(
        (s for s in instance.states if s.vehicle_id == plan.routes[destination].vehicle_id), None
    )
    lower = len(state.executed) if state else 0
    insertion = rng.randrange(lower, len(routes[destination]) + 1)
    routes[destination] = routes[destination][:insertion] + (job,) + routes[destination][insertion:]
    return make_plan(instance, routes)


def swap(instance: RoutingInstance, plan: Plan, rng: random.Random) -> Plan | None:
    choices = movable(instance, plan)
    if len(choices) < 2:
        return None
    (a, i), (b, j) = rng.sample(choices, 2)
    routes = [list(r.stops) for r in plan.routes]
    routes[a][i], routes[b][j] = routes[b][j], routes[a][i]
    return make_plan(instance, [tuple(route) for route in routes])


def reverse_segment(instance: RoutingInstance, plan: Plan, rng: random.Random) -> Plan | None:
    choices = movable(instance, plan)
    if not choices:
        return None
    a, start = rng.choice(choices)
    routes = [r.stops for r in plan.routes]
    end = rng.randrange(start + 1, len(routes[a]) + 1)
    routes[a] = routes[a][:start] + tuple(reversed(routes[a][start:end])) + routes[a][end:]
    # Re-evaluate every directed internal arc, including reversed ones.
    return make_plan(instance, routes)


def destroy_repair(
    instance: RoutingInstance, plan: Plan, rng: random.Random, *, related: bool
) -> Plan | None:
    choices = movable(instance, plan)
    if not choices:
        return None
    count = min(len(choices), max(1, min(20, len(choices) // 5)))
    center = rng.choice(choices)
    if related:
        node = plan.routes[center[0]].stops[center[1]]
        chosen = sorted(
            choices, key=lambda p: (instance.travel[node][plan.routes[p[0]].stops[p[1]]], p)
        )[:count]
    else:
        chosen = rng.sample(choices, count)
    removed = {plan.routes[i].stops[j] for i, j in chosen}
    routes = [tuple(j for j in route.stops if j not in removed) for route in plan.routes]
    repaired = repair(instance, routes, sorted(removed), regret=True)
    return make_plan(instance, repaired) if repaired is not None else None


def two_opt_star(instance: RoutingInstance, plan: Plan, rng: random.Random) -> Plan | None:
    """Exchange two suffixes without modifying committed replanning prefixes."""
    if len(plan.routes) < 2:
        return None
    a, b = rng.sample(range(len(plan.routes)), 2)
    states = {state.vehicle_id: state for state in instance.states}
    first, second = plan.routes[a], plan.routes[b]
    minimum_a = len(states[first.vehicle_id].executed) if first.vehicle_id in states else 0
    minimum_b = len(states[second.vehicle_id].executed) if second.vehicle_id in states else 0
    cut_a = rng.randrange(minimum_a, len(first.stops) + 1)
    cut_b = rng.randrange(minimum_b, len(second.stops) + 1)
    if cut_a == len(first.stops) and cut_b == len(second.stops):
        return None
    routes = [route.stops for route in plan.routes]
    routes[a] = first.stops[:cut_a] + second.stops[cut_b:]
    routes[b] = second.stops[:cut_b] + first.stops[cut_a:]
    return make_plan(instance, routes)


def cross_exchange(instance: RoutingInstance, plan: Plan, rng: random.Random) -> Plan | None:
    """Exchange short contiguous blocks across mutable routes."""
    if len(plan.routes) < 2:
        return None
    a, b = rng.sample(range(len(plan.routes)), 2)
    states = {state.vehicle_id: state for state in instance.states}
    first, second = plan.routes[a], plan.routes[b]
    minimum_a = len(states[first.vehicle_id].executed) if first.vehicle_id in states else 0
    minimum_b = len(states[second.vehicle_id].executed) if second.vehicle_id in states else 0
    if minimum_a >= len(first.stops) or minimum_b >= len(second.stops):
        return None
    start_a = rng.randrange(minimum_a, len(first.stops))
    start_b = rng.randrange(minimum_b, len(second.stops))
    end_a = rng.randrange(start_a + 1, min(len(first.stops), start_a + 3) + 1)
    end_b = rng.randrange(start_b + 1, min(len(second.stops), start_b + 3) + 1)
    routes = [route.stops for route in plan.routes]
    routes[a] = first.stops[:start_a] + second.stops[start_b:end_b] + first.stops[end_a:]
    routes[b] = second.stops[:start_b] + first.stops[start_a:end_a] + second.stops[end_b:]
    return make_plan(instance, routes)
