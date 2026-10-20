"""Versioned Unicode tokenization retaining original character boundaries."""

import unicodedata
from dataclasses import dataclass

LEGACY_TOKENIZER_VERSION = "nfkc-casefold-alnum-v1"
TOKENIZER_VERSION = f"nfkc-casefold-alnum-v2-ucd{unicodedata.unidata_version}"
MAX_DOCUMENT_BYTES = 2_000_000


@dataclass(frozen=True)
class Token:
    term: str
    position: int
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    """NFKC + casefold normalization-safe clusters, retaining source spans.

    Apostrophes and underscores separate tokens. Expansions such as ß→ss retain
    the source character span, so snippets never index into normalized text.
    """
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("document exceeds 2 MB UTF-8 limit")
    normalized: list[tuple[str, int, int]] = []
    i = 0
    while i < len(text):
        end = i + 1
        while end < len(text):
            next_normalized = unicodedata.normalize("NFKC", text[end])
            if unicodedata.category(next_normalized[0]).startswith("M"):
                end += 1
                continue
            if text[end].isascii():
                break
            # A source character can become a combining mark under NFKC
            # (halfwidth Japanese voiced marks), or compose across starters
            # (Hangul). Original Unicode categories alone are insufficient.
            joined = unicodedata.normalize("NFKC", text[i:end]) + next_normalized
            if unicodedata.normalize("NFKC", joined) != joined:
                end += 1
            else:
                break
        normalized.extend(
            (c, i, end) for c in unicodedata.normalize("NFKC", text[i:end]).casefold()
        )
        i = end
    result: list[Token] = []
    term: list[str] = []
    start = 0
    finish = 0
    for char, left, right in normalized:
        if char.isalnum() or (term and unicodedata.category(char).startswith("M")):
            if not term:
                start = left
            term.append(char)
            finish = right
        elif term:
            result.append(Token("".join(term), len(result), start, finish))
            term = []
    if term:
        result.append(Token("".join(term), len(result), start, finish))
    return result
