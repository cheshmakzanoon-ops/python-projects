"""Bounded conjunction parser: terms, quoted phrases, and field:value filters."""

import json
import re
from dataclasses import dataclass

from pp_atlas.ingest.tokenizer import tokenize

MAX_QUERY_BYTES = 4096
MAX_TERMS = 32
MAX_PHRASE_TOKENS = 16
FIELDS = frozenset({"type", "tag", "source", "id"})
_LEX = re.compile(r'\s*(?:"([^"\\]*)"|([^\s"\\]+))')


@dataclass(frozen=True)
class Query:
    terms: tuple[str, ...]
    phrases: tuple[tuple[str, ...], ...]
    filters: tuple[tuple[str, str], ...]

    @property
    def key(self) -> str:
        return json.dumps([self.terms, self.phrases, self.filters], ensure_ascii=False)


def parse(text: str) -> Query:
    if len(text.encode("utf-8")) > MAX_QUERY_BYTES:
        raise ValueError("query exceeds 4096 bytes")
    terms: set[str] = set()
    phrases: list[tuple[str, ...]] = []
    filters: list[tuple[str, str]] = []
    at = 0
    total = 0
    while at < len(text) and text[at:].strip():
        match = _LEX.match(text, at)
        if match is None:
            raise ValueError("malformed query: unmatched quote or unsupported escape")
        at = match.end()
        phrase, word = match.groups()
        if word and ":" in word:
            field, value = word.split(":", 1)
            if field not in FIELDS or not value or len(value) > 256:
                raise ValueError("unknown or invalid filter")
            filters.append((field, value))
            if len(filters) > 8:
                raise ValueError("too many filters")
            continue
        tokens = tuple(t.term for t in tokenize(phrase if phrase is not None else word))
        if not tokens:
            raise ValueError("query operand has no searchable tokens")
        total += len(tokens)
        if total > MAX_TERMS:
            raise ValueError("query exceeds 32 tokens")
        terms.update(tokens)
        if phrase is not None:
            if len(tokens) > MAX_PHRASE_TOKENS:
                raise ValueError("phrase exceeds 16 tokens")
            phrases.append(tokens)
    return Query(tuple(sorted(terms)), tuple(sorted(phrases)), tuple(sorted(set(filters))))
