"""Positional term postings and exact phrase evaluation."""

from collections import defaultdict
from collections.abc import Mapping, Sequence

from pp_atlas.ingest.tokenizer import Token

type Positions = dict[str, tuple[int, ...]]
type Postings = dict[str, dict[str, tuple[int, ...]]]


def positions(tokens: Sequence[Token]) -> Positions:
    result: dict[str, list[int]] = defaultdict(list)
    for token in tokens:
        result[token.term].append(token.position)
    return {term: tuple(value) for term, value in result.items()}


def has_phrase(postings: Mapping[str, tuple[int, ...]], phrase: tuple[str, ...]) -> bool:
    starts = set(postings.get(phrase[0], ()))
    for offset, term in enumerate(phrase[1:], 1):
        starts.intersection_update(p - offset for p in postings.get(term, ()))
    return bool(starts)
