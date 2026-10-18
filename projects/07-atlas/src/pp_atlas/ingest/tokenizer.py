"""Versioned Unicode tokenization retaining original character boundaries."""

import unicodedata
from dataclasses import dataclass

TOKENIZER_VERSION = "nfkc-casefold-alnum-v1"
MAX_DOCUMENT_BYTES = 2_000_000


@dataclass(frozen=True)
class Token:
    term: str
    position: int
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    """NFKC + casefold each grapheme cluster; combining marks join their base.

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
            if unicodedata.category(text[end]).startswith("M"):
                end += 1
                continue
            if text[end].isascii() or text[end - 1].isascii():
                break
            # Hangul composition crosses class-zero starters, including
            # compatibility Jamo. Combining-class-only clustering misses it.
            last_character = unicodedata.normalize("NFKC", text[i:end])[-1]
            next_character = unicodedata.normalize("NFKC", text[end])[0]
            if (
                0x1100 <= ord(last_character) <= 0x1112 and 0x1161 <= ord(next_character) <= 0x1175
            ) or (
                0xAC00 <= ord(last_character) <= 0xD7A3
                and (ord(last_character) - 0xAC00) % 28 == 0
                and 0x11A8 <= ord(next_character) <= 0x11C2
            ):
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
