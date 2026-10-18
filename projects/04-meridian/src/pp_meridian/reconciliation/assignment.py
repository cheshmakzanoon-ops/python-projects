"""Original successive-shortest-augmenting-path min-cost flow, with ambiguity proof.

Each left vertex has an unmatched edge. Bellman-Ford handles residual negative
arcs; integral capacities give a discrete assignment. Removing each selected
edge and resolving detects any equally optimal assignment, including unmatched
alternatives. Bounds apply per connected component, never silently truncate.
"""

from dataclasses import dataclass

from .candidates import ComponentTooLarge, Edge


@dataclass(frozen=True)
class Assignment:
    pairs: tuple[tuple[str, str], ...]
    cost: int
    ambiguous: bool


@dataclass
class Arc:
    end: int
    reverse: int
    capacity: int
    cost: int


def _solve(
    left: list[str], edges: list[Edge], unmatched: int
) -> tuple[tuple[tuple[str, str], ...], int]:
    right = sorted({e.right for e in edges})
    n = len(left) + len(right) + 2
    sink = n - 1
    graph: list[list[Arc]] = [[] for _ in range(n)]

    def add(start: int, end: int, cost: int) -> Arc:
        arc = Arc(end, len(graph[end]), 1, cost)
        graph[start].append(arc)
        graph[end].append(Arc(start, len(graph[start]) - 1, 0, -cost))
        return arc

    li = {key: i + 1 for i, key in enumerate(left)}
    ri = {key: len(left) + i + 1 for i, key in enumerate(right)}
    for i in li.values():
        add(0, i, 0)
        add(i, sink, unmatched)
    for i in ri.values():
        add(i, sink, 0)
    tracked = [
        (e, add(li[e.left], ri[e.right], e.cost))
        for e in sorted(edges, key=lambda e: (e.left, e.right))
    ]
    total = 0
    for _ in left:
        distance: list[int | None] = [None] * n
        distance[0] = 0
        previous: list[tuple[int, int] | None] = [None] * n
        for _ in range(n - 1):
            changed = False
            for start, arcs in enumerate(graph):
                for index, arc in enumerate(arcs):
                    source_distance = distance[start]
                    if not arc.capacity or source_distance is None:
                        continue
                    candidate = source_distance + arc.cost
                    target_distance = distance[arc.end]
                    if target_distance is None or candidate < target_distance:
                        distance[arc.end] = candidate
                        previous[arc.end] = (start, index)
                        changed = True
            if not changed:
                break
        sink_distance = distance[sink]
        assert sink_distance is not None
        total += sink_distance
        end = sink
        while end:
            predecessor = previous[end]
            assert predecessor is not None
            start, index = predecessor
            arc = graph[start][index]
            arc.capacity -= 1
            graph[end][arc.reverse].capacity += 1
            end = start
    return tuple((e.left, e.right) for e, arc in tracked if arc.capacity == 0), total


def solve_component(left: list[str], edges: list[Edge], unmatched: int = 250) -> Assignment:
    if len(left) > 32 or len(edges) > 256:
        raise ComponentTooLarge(
            "component exceeds 32 rows or 256 edges; narrow date/reference scope"
        )
    if len(left) != len(set(left)) or len({(e.left, e.right) for e in edges}) != len(edges):
        raise ValueError("duplicate identities/edges")
    if (
        type(unmatched) is not int
        or unmatched < 0
        or any(e.left not in left or type(e.cost) is not int or e.cost < 0 for e in edges)
    ):
        raise ValueError("invalid graph")
    pairs, cost = _solve(sorted(left), edges, unmatched)
    ambiguous = any(
        _solve(sorted(left), [e for e in edges if (e.left, e.right) != pair], unmatched)[1] == cost
        for pair in pairs
    )
    matched_left = {pair[0] for pair in pairs}
    matched_right = {pair[1] for pair in pairs}
    ambiguous = ambiguous or any(
        e.left not in matched_left and e.right not in matched_right and e.cost == unmatched
        for e in edges
    )
    return Assignment(pairs, cost, ambiguous)


def solve(left: list[str], edges: list[Edge], unmatched: int = 250) -> list[Assignment]:
    """Split sparse graph by connected components, including isolated rows."""
    left_set = set(left)
    if len(left) != len(left_set) or any(edge.left not in left_set for edge in edges):
        raise ValueError("invalid left identities")
    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for key in left:
        adjacency[("l", key)] = set()
    for edge in edges:
        a, b = ("l", edge.left), ("r", edge.right)
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    edges_by_left: dict[str, list[Edge]] = {}
    for edge in edges:
        edges_by_left.setdefault(edge.left, []).append(edge)
    seen: set[tuple[str, str]] = set()
    results = []
    for vertex in sorted(adjacency):
        if vertex in seen:
            continue
        stack = [vertex]
        component: set[tuple[str, str]] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        seen |= component
        keys = sorted(key for side, key in component if side == "l")
        results.append(
            solve_component(
                keys, [edge for key in keys for edge in edges_by_left.get(key, [])], unmatched
            )
        )
    return results
