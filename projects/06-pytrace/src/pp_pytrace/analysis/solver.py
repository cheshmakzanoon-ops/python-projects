"""Worklist convergence, independent of Python syntax and diagnostic emission."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from pp_pytrace.analysis.lattice import Environment, environment_key, join_environments
from pp_pytrace.cfg.blocks import Block, Graph


@dataclass(frozen=True)
class Solution:
    states: dict[int, Environment]
    iterations: int


@dataclass(frozen=True)
class Effects:
    normal: Environment
    exceptional: Environment | None = None


def solve(
    graph: Graph,
    initial: Environment,
    transfer: Callable[[Block, Environment], Environment | Effects],
    *,
    max_steps: int = 100_000,
) -> Solution:
    """Compute incoming may-states; transfer must not mutate its incoming state.

    Normal edges receive completed effects. An exceptional edge receives the
    join of state before and after the block, covering failure before assignment
    publication as well as expression side effects preceding a later failure.
    Evidence-only changes do not schedule a semantic transfer.
    """
    states = {graph.entry: dict(initial)}
    queue = deque([graph.entry])
    pending = {graph.entry}
    iterations = 0
    while queue:
        if iterations >= max_steps:
            raise ValueError(f"Dataflow analysis exceeds {max_steps} transfer steps")
        index = queue.popleft()
        pending.remove(index)
        iterations += 1
        block = graph.blocks[index]
        result = transfer(block, states[index])
        output = result.normal if isinstance(result, Effects) else result
        edges = [(block.successors, output)]
        if block.exceptional_successors:
            failure = join_environments(states[index], output)
            if isinstance(result, Effects) and result.exceptional is not None:
                failure = join_environments(failure, result.exceptional)
            edges.append((block.exceptional_successors, failure))
        for targets, state in edges:
            for destination in targets:
                previous = states.get(destination)
                merged = state if previous is None else join_environments(previous, state)
                changed = previous is None or environment_key(previous) != environment_key(merged)
                states[destination] = merged
                if changed and destination not in pending:
                    queue.append(destination)
                    pending.add(destination)
    return Solution(states, iterations)
