"""Finite concrete-state exploration is independent of the abstract worklist."""

from __future__ import annotations

from collections import deque

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pp_pytrace.analysis.lattice import Value
from pp_pytrace.analysis.solver import solve
from pp_pytrace.cfg.blocks import Block, Graph


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.sampled_from(["preserve", "source", "clear"]), min_size=2, max_size=15), st.data()
)
def test_fixed_point_matches_exhaustive_boolean_path_semantics(
    operations: list[str], data: st.DataObject
) -> None:
    size = len(operations)
    edges = data.draw(
        st.lists(st.tuples(st.integers(0, size - 1), st.integers(0, size - 1)), max_size=40)
    )
    blocks = {index: Block(index, None) for index in range(size)}
    for origin, destination in edges:
        blocks[origin].successors.append(destination)
    graph = Graph(blocks, 0)

    def transfer(block: Block, incoming: dict[str, Value]) -> dict[str, Value]:
        value = incoming["value"].taint
        if operations[block.index] == "source":
            value = 1
        elif operations[block.index] == "clear":
            value = 0
        return {"value": Value(taint=value)}

    concrete: dict[int, set[bool]] = {}
    pending = deque([(0, False)])
    while pending:
        index, tainted = pending.popleft()
        if tainted in concrete.setdefault(index, set()):
            continue
        concrete[index].add(tainted)
        result = (
            True
            if operations[index] == "source"
            else False
            if operations[index] == "clear"
            else tainted
        )
        pending.extend((destination, result) for destination in blocks[index].successors)
    answer = solve(graph, {"value": Value()}, transfer)
    assert set(answer.states) == set(concrete)
    for index, states in concrete.items():
        assert bool(answer.states[index]["value"].taint) == any(states)
    # Reversing successor scheduling must not change the semantic result.
    for block in blocks.values():
        block.successors.reverse()
    reordered = solve(graph, {"value": Value()}, transfer)
    assert {index: env["value"].key for index, env in answer.states.items()} == {
        index: env["value"].key for index, env in reordered.states.items()
    }


def test_work_budget_fails_without_returning_an_incomplete_solution() -> None:
    graph = Graph({0: Block(0, None, [1]), 1: Block(1, None)}, 0)
    with pytest.raises(ValueError, match="transfer steps"):
        solve(graph, {"value": Value()}, lambda block, env: dict(env), max_steps=1)
