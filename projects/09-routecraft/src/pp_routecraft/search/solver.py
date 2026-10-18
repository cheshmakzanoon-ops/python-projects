"""Seeded adaptive large-neighborhood search with a separately retained incumbent."""

import math
import random
import time
from collections.abc import Callable

from pp_routecraft.construction.insertion import construct
from pp_routecraft.domain.instance import (
    Plan,
    Route,
    RoutingInstance,
    SearchBudget,
    SolveResult,
    Status,
)
from pp_routecraft.neighborhoods.moves import destroy_repair, relocate, reverse_segment, swap
from pp_routecraft.validation.verifier import input_errors, verify


def solve(
    instance: RoutingInstance,
    budget: SearchBudget = SearchBudget(),
    *,
    seed: int = 1729,
    cancelled: Callable[[], bool] | None = None,
    initial: Plan | None = None,
) -> SolveResult:
    started = time.monotonic()
    errors = list(input_errors(instance))
    valid_seconds = True
    if budget.seconds is not None:
        try:
            valid_seconds = (
                type(budget.seconds) in (int, float)
                and budget.seconds >= 0
                and math.isfinite(budget.seconds)
            )
        except OverflowError:
            valid_seconds = False
    if type(budget.iterations) is not int or budget.iterations < 0 or not valid_seconds:
        errors.append("budget must have finite nonnegative limits")
    if errors:
        return SolveResult(
            Status.INVALID_INPUT,
            None,
            0,
            "invalid_input",
            time.monotonic() - started,
            None,
            (),
            (),
            tuple(errors),
        )
    if initial is not None and not verify(instance, initial).valid:
        return SolveResult(
            Status.INVALID_INPUT,
            None,
            0,
            "invalid_incumbent",
            time.monotonic() - started,
            None,
            (),
            (),
            ("initial plan failed independent verification",),
        )
    best = initial
    if initial is not None:
        # Public plans may omit idle vehicles or order routes arbitrarily. The
        # neighborhood representation uses the instance's full vehicle order.
        routes = {route.vehicle_id: route for route in initial.routes}
        best = Plan(
            tuple(routes.get(vehicle.id, Route(vehicle.id, ())) for vehicle in instance.vehicles),
            initial.objective,
            initial.schema_version,
        )
    first = 0.0 if initial else None
    reason = "iteration_budget"
    trajectory: list[tuple[int, int, int]] = []
    rng = random.Random(seed)
    names = ("relocate", "swap", "reverse", "random_destroy", "related_destroy")
    weights = [1.0] * len(names)
    counts = [0] * len(names)
    if best is None:
        # Budget includes construction. Check deadlines before entering it; once
        # started, a constructor is an atomic bounded operation, not preemptible.
        if cancelled is not None and cancelled():
            reason = "cancelled"
        elif budget.seconds is not None and time.monotonic() - started >= budget.seconds:
            reason = "wall_clock"
        else:
            best = construct(instance, regret=False)
            if best is None:
                best = construct(instance, regret=True)
            if best is not None:
                report = verify(instance, best)
                if not report.valid:
                    raise RuntimeError(
                        f"constructor violated independent verifier: {report.errors}"
                    )
                first = time.monotonic() - started
    current = best
    if best:
        trajectory.append((0, *best.objective))
    iterations = 0
    for iteration in range(1, budget.iterations + 1):
        if cancelled is not None and cancelled():
            reason = "cancelled"
            break
        if budget.seconds is not None and time.monotonic() - started >= budget.seconds:
            reason = "wall_clock"
            break
        iterations = iteration
        operator = rng.choices(range(len(names)), weights=weights, k=1)[0]
        counts[operator] += 1
        candidate: Plan | None
        if current is None:
            candidate = construct(instance, regret=True)
        elif operator == 0:
            candidate = relocate(instance, current, rng)
        elif operator == 1:
            candidate = swap(instance, current, rng)
        elif operator == 2:
            candidate = reverse_segment(instance, current, rng)
        else:
            candidate = destroy_repair(instance, current, rng, related=operator == 4)
        reward = 0.2
        if candidate is not None:
            report = verify(instance, candidate)
            if not report.valid:
                # A broken operator is not allowed to corrupt a proven incumbent.
                candidate = None
            else:
                if best is None or candidate.objective < best.objective:
                    best = candidate
                    first = first if first is not None else time.monotonic() - started
                    trajectory.append((iteration, *best.objective))
                    reward = 6.0
                if current is None or candidate.objective <= current.objective:
                    current = candidate
                    reward = max(reward, 2.0)
                elif candidate.objective[0] == current.objective[0]:
                    # Annealing permits travel deterioration, never hard violations.
                    temperature = max(1.0, 30.0 * (1 - iteration / max(1, budget.iterations)))
                    deterioration = candidate.objective[1] - current.objective[1]
                    # More-negative exponents underflow to zero anyway. Compare
                    # the integer first so arbitrary-size costs never overflow
                    # during the conversion to floating-point probability.
                    probability = (
                        0.0
                        if deterioration > 746 * temperature
                        else math.exp(-deterioration / temperature)
                    )
                    if rng.random() < probability:
                        current = candidate
        weights[operator] = 0.8 * weights[operator] + 0.2 * reward
    if best is not None and not verify(instance, best).valid:
        raise RuntimeError("retained incumbent failed independent verification")
    return SolveResult(
        Status.FEASIBLE if best is not None else Status.NO_FEASIBLE_PLAN_FOUND,
        best,
        iterations,
        reason,
        time.monotonic() - started,
        first,
        tuple(trajectory),
        tuple(zip(names, counts, strict=True)),
    )
