"""Independent complete enumeration of sparse partial assignments."""

from itertools import product
from random import Random

from pp_meridian.reconciliation.assignment import solve
from pp_meridian.reconciliation.candidates import Edge


def optimal_assignments(left, edges, unmatched):
    costs = {(edge.left, edge.right): edge.cost for edge in edges}
    choices = [[None] + [right for row, right in costs if row == key] for key in left]
    minimum = None
    optima = set()
    for assignment in product(*choices):
        occupied = [right for right in assignment if right is not None]
        if len(occupied) != len(set(occupied)):
            continue
        cost = sum(
            unmatched if right is None else costs[key, right]
            for key, right in zip(left, assignment, strict=True)
        )
        pairs = frozenset(
            (key, right) for key, right in zip(left, assignment, strict=True) if right is not None
        )
        if minimum is None or cost < minimum:
            minimum, optima = cost, {pairs}
        elif cost == minimum:
            optima.add(pairs)
    return minimum, optima


def test_sparse_components_match_all_partial_assignment_optima():
    rng = Random(61783)
    for case in range(400):
        left = [f"L{i}" for i in range(rng.randrange(1, 5))]
        right = [f"R{i}" for i in range(rng.randrange(1, 5))]
        unmatched = rng.randrange(9)
        edges = [
            Edge(row, posting, rng.randrange(9))
            for row in left
            for posting in right
            if rng.random() < 0.65
        ]
        minimum, optima = optimal_assignments(left, edges, unmatched)
        result = solve(left, edges, unmatched)
        selected = frozenset(pair for component in result for pair in component.pairs)
        assert sum(component.cost for component in result) == minimum, case
        assert selected in optima, case
        assert any(component.ambiguous for component in result) == (len(optima) > 1), case
        reordered = solve(list(reversed(left)), list(reversed(edges)), unmatched)
        assert frozenset(pair for component in reordered for pair in component.pairs) == selected
