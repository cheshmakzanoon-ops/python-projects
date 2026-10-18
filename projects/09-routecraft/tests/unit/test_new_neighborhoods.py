"""Safety and reproducibility for inter-route neighborhood operators."""

import random

from pp_routecraft import construct, verify
from pp_routecraft.fixtures import island
from pp_routecraft.neighborhoods.moves import cross_exchange, two_opt_star


def test_new_operators_respect_independent_verifier() -> None:
    instance = island(25)
    initial = construct(instance)
    assert initial is not None
    for operation in (two_opt_star, cross_exchange):
        for seed in range(25):
            candidate = operation(instance, initial, random.Random(seed))
            assert candidate is None or verify(instance, candidate).valid
            assert candidate == operation(instance, initial, random.Random(seed))
