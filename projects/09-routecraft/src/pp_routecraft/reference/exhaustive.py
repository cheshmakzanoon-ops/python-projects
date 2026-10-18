"""Independent permutation/partition enumeration for <=6 customers, <=2 vehicles.

No production scheduler or neighborhood code is reused. Every labeled assignment
and ordering is represented by a permutation and all weak route compositions.
"""

import itertools
import time
from collections.abc import Iterator

from pp_routecraft.domain.instance import Plan, Route, RoutingInstance, SolveResult, Status
from pp_routecraft.validation.verifier import input_errors, verify


def _sizes(total: int, count: int) -> Iterator[tuple[int, ...]]:
    if count == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for tail in _sizes(total - first, count - 1):
                yield (first,) + tail


def exhaustive(instance: RoutingInstance) -> SolveResult:
    started = time.monotonic()
    errors = input_errors(instance)
    if errors:
        return SolveResult(
            Status.INVALID_INPUT, None, 0, "invalid_input", 0.0, None, (), (), errors
        )
    if len(instance.stops) > 6 or len(instance.vehicles) > 2 or instance.states:
        raise ValueError("reference supports at most six customers, two vehicles, no snapshots")
    best: Plan | None = None
    checked = 0
    first: float | None = None
    for order in itertools.permutations(s.id for s in instance.stops):
        for sizes in _sizes(len(order), len(instance.vehicles)):
            routes: list[Route] = []
            offset = 0
            travel = 0
            for vehicle, size in zip(instance.vehicles, sizes, strict=True):
                jobs = order[offset : offset + size]
                offset += size
                node = 0
                for job in jobs:
                    travel += instance.travel[node][job]
                    node = job
                if jobs:
                    travel += instance.travel[node][0]
                routes.append(Route(vehicle.id, jobs))
            objective = (sum(bool(r.stops) for r in routes), travel)
            checked += 1
            if best is not None and objective >= best.objective:
                continue
            candidate = Plan(tuple(routes), objective)
            report = verify(instance, candidate)
            if report.valid:
                best = candidate
                if first is None:
                    first = time.monotonic() - started
    return SolveResult(
        Status.OPTIMAL if best else Status.PROVEN_INFEASIBLE,
        best,
        checked,
        "exhaustive_enumeration",
        time.monotonic() - started,
        first,
        (),
        (("enumerated_plans", checked),),
        optimality_gap="0" if best else "unknown",
    )
