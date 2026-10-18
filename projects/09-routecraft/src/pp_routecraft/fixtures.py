"""All demo and benchmark inputs are authored synthetic integer-unit fixtures."""

import math
import random
from dataclasses import replace

from pp_routecraft.domain.instance import (
    LoadedJob,
    Plan,
    RoutingInstance,
    Stop,
    Vehicle,
    VehicleState,
)
from pp_routecraft.replanning.rolling import prepare_replan
from pp_routecraft.validation.verifier import verify


def island(customers: int = 25, seed: int = 1729, *, tight: bool = False) -> RoutingInstance:
    if customers < 1:
        raise ValueError("customer count must be positive")
    rng = random.Random(seed)
    coordinates = [(0.0, 0.0)] + [
        (rng.uniform(-20, 20), rng.uniform(-12, 12)) for _ in range(customers)
    ]
    matrix = tuple(
        tuple(
            0 if i == j else max(1, int(math.dist(a, b) * 3) + ((i * 13 + j * 7 + seed) % 13))
            for j, b in enumerate(coordinates)
        )
        for i, a in enumerate(coordinates)
    )
    # Plenty of fleet capacity; time windows are tight relative to the 10000-unit
    # shift, with an independently obvious one-customer-per-vehicle witness.
    stops = tuple(
        Stop(
            i,
            rng.randint(1, 3),
            (i % 4) * 40 if tight else 0,
            600 if tight else 10000,
            3,
            *coordinates[i],
        )
        for i in range(1, customers + 1)
    )
    fleet = max(2, math.ceil(customers / 4))
    return RoutingInstance(stops, tuple(Vehicle(i, 16, 0, 10000) for i in range(fleet)), matrix)


def tiny(*, impossible: bool = False) -> RoutingInstance:
    return RoutingInstance(
        (Stop(1, 1, 0, 20), Stop(2, 1, 0, 20), Stop(3, 1, 0, 20)),
        (Vehicle(0, 1 if impossible else 3, 0, 20), Vehicle(1, 1 if impossible else 3, 0, 20)),
        ((0, 2, 5, 6), (7, 0, 2, 8), (4, 9, 0, 2), (2, 3, 8, 0)),
    )


def new_request(instance: RoutingInstance, plan: Plan) -> RoutingInstance:
    """Freeze one real completed service, adding a genuinely unloaded new job."""
    report = verify(instance, plan)
    if not report.valid:
        raise ValueError("snapshot needs a verified original plan")
    active = next((r for r in plan.routes if r.stops), None)
    if active is None:
        raise ValueError("snapshot needs a nonempty route")
    completed = active.stops[:1]
    schedule = next(visits for vid, visits, _ in report.schedules if vid == active.vehicle_id)
    states: list[VehicleState] = []
    for vehicle in instance.vehicles:
        if vehicle.id == active.vehicle_id:
            loaded = tuple(LoadedJob(j, instance.stops[j - 1].demand) for j in active.stops[1:])
            states.append(
                VehicleState(
                    vehicle.id,
                    True,
                    completed,
                    completed[-1],
                    schedule[0].departure,
                    sum(j.quantity for j in loaded),
                    loaded,
                )
            )
        else:
            states.append(VehicleState(vehicle.id, False, (), 0, vehicle.start, 0, ()))
    new_id = len(instance.stops) + 1
    old_n = len(instance.travel)
    expanded = tuple(tuple(row) + (10 + i % 7,) for i, row in enumerate(instance.travel))
    expanded += (tuple(13 + i % 5 for i in range(old_n)) + (0,),)
    updated = replace(
        instance, stops=instance.stops + (Stop(new_id, 1, 0, 10000, 3, 2.0, 2.0),), travel=expanded
    )
    return prepare_replan(instance, plan, updated, tuple(states))
