"""Bounded sparse graph with amount/currency/date buckets and component guards."""

from dataclasses import dataclass
from datetime import date, datetime

from .normalize import normalize_reference

DEFAULT_WINDOW_DAYS = 7


class ComponentTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class MatchEntry:
    identity: str
    amount: int
    currency: str
    timestamp: datetime
    reference: str


@dataclass(frozen=True)
class Edge:
    left: str
    right: str
    cost: int


def candidates(
    rows: list[MatchEntry], postings: list[MatchEntry], days: int = DEFAULT_WINDOW_DAYS
) -> list[Edge]:
    if not 0 <= days <= 31:
        raise ValueError("date window must be 0..31 days")
    buckets: dict[tuple[int, str, object], list[MatchEntry]] = {}
    for posting in postings:
        buckets.setdefault((posting.amount, posting.currency, posting.timestamp.date()), []).append(
            posting
        )
    parent: dict[tuple[str, str], tuple[str, str]] = {}
    counts: dict[tuple[str, str], tuple[int, int]] = {}

    def root(vertex: tuple[str, str]) -> tuple[str, str]:
        if vertex not in parent:
            parent[vertex] = vertex
            counts[vertex] = (int(vertex[0] == "l"), 0)
        current = vertex
        while parent[current] != current:
            current = parent[current]
        while parent[vertex] != vertex:
            previous = parent[vertex]
            parent[vertex] = current
            vertex = previous
        return current

    edges = []
    for row in rows:
        ordinal = row.timestamp.date().toordinal()
        for offset in range(-days, days + 1):
            candidate_day = ordinal + offset
            if not date.min.toordinal() <= candidate_day <= date.max.toordinal():
                continue
            for posting in buckets.get(
                (row.amount, row.currency, date.fromordinal(candidate_day)), []
            ):
                a, b = root(("l", row.identity)), root(("r", posting.identity))
                left_count, edge_count = counts[a]
                if a != b:
                    right_count, right_edges = counts[b]
                    left_count += right_count
                    edge_count += right_edges
                    parent[b] = a
                edge_count += 1
                if left_count > 32 or edge_count > 256:
                    raise ComponentTooLarge(
                        "component exceeds 32 rows or 256 edges during candidate construction"
                    )
                counts[a] = (left_count, edge_count)
                exact = bool(row.reference) and normalize_reference(
                    row.reference
                ) == normalize_reference(posting.reference)
                edges.append(
                    Edge(row.identity, posting.identity, abs(offset) * 10 + (0 if exact else 100))
                )
    return edges
