"""Positional term postings and exact phrase evaluation."""

from bisect import bisect_left
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
    """Probe sorted positional lists from the rarest phrase occurrence.

    No full posting is copied. For m terms and r anchor positions the working
    memory is O(m), and probes cost O(r*m*log(f)), f the longest posting. This
    favors selective phrases; equally frequent nonmatches can require more CPU
    than linear intersection. Empty phrases are not produced by the query parser.
    """
    lists = [postings.get(term, ()) for term in phrase]
    if not lists or any(not values for values in lists):
        return False
    anchor = min(range(len(lists)), key=lambda offset: len(lists[offset]))
    for position in lists[anchor]:
        start = position - anchor
        if start < 0:
            continue
        for offset, values in enumerate(lists):
            if offset == anchor:
                continue
            index = bisect_left(values, start + offset)
            if index == len(values) or values[index] != start + offset:
                break
        else:
            return True
    return False
