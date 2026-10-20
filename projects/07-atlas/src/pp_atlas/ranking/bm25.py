"""Original scalar BM25 implementation; statistics always come from visibility."""

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pp_atlas.index.segments import Record


@dataclass(frozen=True)
class Scorer:
    """A query's visible statistics; candidate scores need no explanation dict."""

    terms: tuple[str, ...]
    count: int
    document_frequencies: Mapping[str, int]
    average_length: float
    k1: float
    b: float

    def _parts(self, record: Record) -> Iterator[tuple[str, float]]:
        for term in self.terms:
            yield (
                term,
                contribution(
                    len(record.positions[term]),
                    record.length,
                    self.count,
                    self.document_frequencies[term],
                    self.average_length,
                    k1=self.k1,
                    b=self.b,
                ),
            )

    def score(self, record: Record) -> float:
        return sum(value for _, value in self._parts(record))

    def explain(self, record: Record) -> dict[str, float]:
        return dict(self._parts(record))


def contribution(
    frequency: int,
    length: int,
    count: int,
    document_frequency: int,
    average_length: float,
    *,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    if not math.isfinite(k1) or k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires finite k1 > 0 and 0 <= b <= 1")
    if not frequency or not count or not average_length:
        return 0.0
    if not 0 < document_frequency <= count:
        raise ValueError("invalid visible document frequency")
    idf = math.log1p((count - document_frequency + 0.5) / (document_frequency + 0.5))
    norm = k1 * (1 - b + b * length / average_length)
    return idf * frequency * (k1 + 1) / (frequency + norm)
