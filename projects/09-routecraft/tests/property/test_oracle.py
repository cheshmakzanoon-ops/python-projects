"""Generated directed matrices vs a complete permutation/partition reference."""

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_routecraft import (
    RoutingInstance,
    SearchBudget,
    Status,
    Stop,
    Vehicle,
    exhaustive,
    solve,
    verify,
)
from pp_routecraft.construction.insertion import construct


@settings(max_examples=25, deadline=None)
@given(st.integers(1, 5), st.integers(0, 100000), st.integers(1, 6))
def test_tiny_oracle_bounds_and_independent_verification(n: int, seed: int, capacity: int) -> None:
    import random

    rng = random.Random(seed)
    matrix = tuple(
        tuple(0 if i == j else rng.randint(1, 12) for j in range(n + 1)) for i in range(n + 1)
    )
    instance = RoutingInstance(
        tuple(Stop(i, 1) for i in range(1, n + 1)),
        (Vehicle(0, capacity), Vehicle(1, capacity)),
        matrix,
    )
    reference = exhaustive(instance)
    result = solve(instance, SearchBudget(70), seed=seed)
    if 2 * capacity < n:
        assert reference.status == Status.PROVEN_INFEASIBLE
        assert result.status == Status.NO_FEASIBLE_PLAN_FOUND
    else:
        assert reference.status == Status.OPTIMAL
        assert reference.plan is not None and verify(instance, reference.plan).valid
        assert result.plan is not None and verify(instance, result.plan).valid
        assert reference.plan.objective <= result.plan.objective
        assert reference.plan.objective[0] == (n + capacity - 1) // capacity
    for regret in (False, True):
        candidate = construct(instance, regret=regret)
        assert candidate is None or verify(instance, candidate).valid


@settings(max_examples=30, deadline=None)
@given(st.integers(1, 30), st.integers(0, 1000), st.booleans())
def test_generated_islands_never_publish_invalid_plan(n: int, seed: int, tight: bool) -> None:
    from pp_routecraft.fixtures import island

    instance = island(n, seed, tight=tight)
    result = solve(instance, SearchBudget(12), seed=seed)
    assert result.status == Status.FEASIBLE
    assert result.plan is not None and verify(instance, result.plan).valid
