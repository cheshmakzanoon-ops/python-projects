"""Insertion certificates against direct simulation on arbitrary directed arcs."""

import itertools
import random
from dataclasses import replace

from pp_routecraft import (
    LoadedJob,
    Plan,
    Route,
    RoutingInstance,
    Status,
    Stop,
    Vehicle,
    VehicleState,
    exhaustive,
    verify,
)
from pp_routecraft.construction.insertion import evaluate_route, options


def route_truth(instance: RoutingInstance, jobs: tuple[int, ...]) -> int | None:
    """Direct test-only simulation; neither production scheduler nor verifier used."""
    vehicle = instance.vehicles[0]
    state = instance.states[0] if instance.states else None
    prefix = state.executed if state else ()
    if jobs[: len(prefix)] != prefix:
        return None
    if (
        state
        and state.started
        and not set(jobs[len(prefix) :]) <= {job.stop_id for job in state.loaded}
    ):
        return None
    cargo = (
        state.onboard + sum(instance.stops[j - 1].demand for j in prefix)
        if state and state.started
        else sum(instance.stops[j - 1].demand for j in jobs)
    )
    if cargo > vehicle.capacity:
        return None
    clock, location, distance = vehicle.start, 0, 0
    for position, node in enumerate(jobs):
        if state and position == len(prefix):
            if clock > state.time:
                return None
            clock = state.time
        stop = instance.stops[node - 1]
        distance += instance.travel[location][node]
        clock = max(clock + instance.travel[location][node], stop.ready)
        if clock > stop.due:
            return None
        clock += stop.service
        cargo -= stop.demand
        if clock > vehicle.end or cargo < 0:
            return None
        location = node
    if state and len(prefix) == len(jobs):
        if clock > state.time:
            return None
        clock = state.time
    if jobs:
        distance += instance.travel[location][0]
        clock += instance.travel[location][0]
    return distance if clock <= vehicle.end else None


def test_all_insertion_positions_match_unindexed_simulation() -> None:
    rng = random.Random(611271)
    positions_checked = 0
    for case in range(600):
        count = rng.randint(2, 10)
        travel = tuple(
            tuple(0 if a == b else rng.randrange(15) for b in range(count + 1))
            for a in range(count + 1)
        )
        stops = tuple(
            Stop(node, rng.randint(1, 3), rng.randrange(20), rng.randint(30, 140), rng.randrange(5))
            for node in range(1, count + 1)
        )
        vehicle = Vehicle(7, 40, rng.randrange(5), rng.randint(45, 160))
        instance = RoutingInstance(stops, (vehicle,), travel)
        route = list(range(1, count + 1))
        rng.shuffle(route)
        prefix_length = rng.randrange(count)
        inserted = route.pop(rng.randrange(prefix_length, count))
        if case % 2:
            prefix = tuple(route[:prefix_length])
            clock, last = vehicle.start, 0
            for node in prefix:
                stop = stops[node - 1]
                clock = max(clock + travel[last][node], stop.ready) + stop.service
                last = node
            suffix = tuple(route[prefix_length:]) + (inserted,)
            loaded = tuple(LoadedJob(node, stops[node - 1].demand) for node in suffix)
            state = VehicleState(
                7,
                True,
                prefix,
                prefix[-1] if prefix else 0,
                clock + rng.randrange(5),
                sum(job.quantity for job in loaded),
                loaded,
            )
            instance = replace(instance, states=(state,))
        else:
            prefix_length = 0
        jobs = tuple(route)
        evaluated = evaluate_route(instance, 0, jobs)
        assert (evaluated[1] if evaluated else None) == route_truth(instance, jobs)
        raw_cost = sum(travel[a][b] for a, b in zip((0, *jobs), (*jobs, 0), strict=True))
        expected = {}
        for position in range(prefix_length, len(jobs) + 1):
            truth = route_truth(instance, jobs[:position] + (inserted,) + jobs[position:])
            positions_checked += 1
            if truth is not None:
                expected[position] = (truth, (int(not jobs), truth - raw_cost))
        actual = {
            candidate.position: (candidate.travel, candidate.delta)
            for candidate in options(instance, [jobs], inserted)
        }
        assert actual == expected, (case, jobs, inserted, expected, actual)
    assert positions_checked >= 2000


def test_exact_reference_matches_independent_labeled_assignment_enumeration() -> None:
    rng = random.Random(702813)
    for _ in range(35):
        count = rng.randint(1, 5)
        vehicles = (Vehicle(3, rng.randint(1, 6), end=30), Vehicle(8, rng.randint(1, 6), 2, 35))
        instance = RoutingInstance(
            tuple(
                Stop(
                    node, rng.randint(1, 2), rng.randrange(8), rng.randint(8, 30), rng.randrange(4)
                )
                for node in range(1, count + 1)
            ),
            vehicles,
            tuple(
                tuple(0 if a == b else rng.randrange(12) for b in range(count + 1))
                for a in range(count + 1)
            ),
        )
        expected = None
        # Assignment first, then each route permutation: independent of the
        # reference's global permutation/weak-composition enumeration.
        for assignment in itertools.product(range(2), repeat=count):
            buckets = [
                tuple(node for node in range(1, count + 1) if assignment[node - 1] == index)
                for index in range(2)
            ]
            for routes in itertools.product(
                *(itertools.permutations(bucket) for bucket in buckets)
            ):
                costs = [
                    route_truth(replace(instance, vehicles=(vehicle,)), jobs)
                    for vehicle, jobs in zip(vehicles, routes, strict=True)
                ]
                travel = sum(
                    instance.travel[a][b]
                    for jobs in routes
                    for a, b in zip((0, *jobs), (*jobs, 0), strict=True)
                )
                objective = (sum(bool(jobs) for jobs in routes), travel)
                candidate = Plan(
                    tuple(
                        Route(vehicle.id, jobs)
                        for vehicle, jobs in zip(vehicles, routes, strict=True)
                    ),
                    objective,
                )
                assert verify(instance, candidate).valid == all(cost is not None for cost in costs)
                if any(cost is None for cost in costs):
                    continue
                if expected is None or objective < expected:
                    expected = objective
        exact = exhaustive(instance)
        assert exact.status == (
            Status.OPTIMAL if expected is not None else Status.PROVEN_INFEASIBLE
        )
        assert (exact.plan.objective if exact.plan else None) == expected


def test_insertion_eligibility_matches_independent_multi_vehicle_cargo_assignment() -> None:
    rng = random.Random(91341)
    for _ in range(150):
        count = rng.randint(2, 8)
        vehicles = (Vehicle(8, 20), Vehicle(3, 20), Vehicle(17, 20))
        ownership = {node: rng.choice((None, 1, 2)) for node in range(1, count + 1)}
        inserted = rng.randrange(1, count + 1)
        states = tuple(
            VehicleState(
                vehicle.id,
                index > 0,
                (),
                0,
                0,
                sum(owner == index for owner in ownership.values()) if index else 0,
                tuple(LoadedJob(node, 1) for node, owner in ownership.items() if owner == index)
                if index
                else (),
            )
            for index, vehicle in enumerate(vehicles)
        )
        travel = tuple(
            tuple(0 if a == b else rng.randrange(40) for b in range(count + 1))
            for a in range(count + 1)
        )
        instance = RoutingInstance(
            tuple(Stop(node, 1) for node in range(1, count + 1)), vehicles, travel, states=states
        )
        routes = [
            tuple(
                node
                for node, owner in ownership.items()
                if node != inserted and (owner == index if index else owner is None)
            )
            for index in range(3)
        ]
        target = ownership[inserted] or 0
        jobs = routes[target]
        expected = {(target, position) for position in range(len(jobs) + 1)}
        actual = {
            (candidate.vehicle_index, candidate.position)
            for candidate in options(instance, routes, inserted)
        }
        assert actual == expected, (ownership, inserted, actual, expected)
