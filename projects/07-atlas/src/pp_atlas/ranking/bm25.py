"""Original scalar BM25 implementation; statistics always come from visibility."""

import math


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
