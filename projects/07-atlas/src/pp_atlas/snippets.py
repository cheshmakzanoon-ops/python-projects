"""Source-aligned HTML excerpts; original text and markup are always escaped."""

import html
from collections.abc import Sequence

from pp_atlas.ingest.tokenizer import Token


def snippet(text: str, tokens: Sequence[Token], terms: frozenset[str], width: int = 240) -> str:
    hits = [(t.start, t.end) for t in tokens if t.term in terms]
    center = hits[0][0] if hits else 0
    left = max(0, center - width // 3)
    right = min(len(text), left + width)
    pieces = ["…" if left else ""]
    cursor = left
    for start, end in hits:
        if start < cursor or start >= right:
            continue
        pieces.extend(
            [
                html.escape(text[cursor:start]),
                "<mark>",
                html.escape(text[start : min(end, right)]),
                "</mark>",
            ]
        )
        cursor = min(end, right)
    pieces.append(html.escape(text[cursor:right]))
    if right < len(text):
        pieces.append("…")
    return "".join(pieces)
