"""Whole-string Unicode and direct sliding-window/mathematical reference models."""

import itertools
import math
import unicodedata
from collections import Counter

import pytest

from pp_atlas import Document, Engine, Principal
from pp_atlas.index.postings import has_phrase
from pp_atlas.ingest.tokenizer import tokenize


def whole_string_terms(source):
    terms = []
    word = ""
    for char in unicodedata.normalize("NFKC", source).casefold():
        if char.isalnum() or (word and unicodedata.category(char).startswith("M")):
            word += char
        elif word:
            terms.append(word)
            word = ""
    return terms + ([word] if word else [])


def test_normalization_boundaries_against_whole_string_oracle():
    alphabet = ["a", "A", "カ", "ｶ", "ﾊ", "ﾞ", "ﾟ", "\u0300", "\u3099", "ᄀ", "ᅡ", "ᆨ", "ㄱ", "ㅏ", " "]
    for size in range(4):
        for characters in itertools.product(alphabet, repeat=size):
            source = "".join(characters)
            actual = tokenize(source)
            assert [token.term for token in actual] == whole_string_terms(source), repr(source)
            assert all(0 <= t.start < t.end <= len(source) for t in actual)


def test_phrase_positions_against_exhaustive_sliding_windows():
    for length in range(7):
        for words in itertools.product(("a", "b"), repeat=length):
            positions = {
                term: tuple(i for i, word in enumerate(words) if word == term)
                for term in set(words)
            }
            for phrase_length in range(1, 5):
                for phrase in itertools.product(("a", "b"), repeat=phrase_length):
                    expected = any(
                        words[i : i + phrase_length] == phrase
                        for i in range(length - phrase_length + 1)
                    )
                    assert has_phrase(positions, phrase) == expected


def test_rare_phrase_anchor_does_not_scan_common_posting():
    class CountedTuple(tuple):
        reads = 0

        def __iter__(self):
            for value in super().__iter__():
                self.reads += 1
                yield value

        def __getitem__(self, index):
            self.reads += 1
            return super().__getitem__(index)

    common = CountedTuple(range(100_000))
    assert has_phrase({"common": common, "rare": (100_000,)}, ("common", "rare"))
    assert common.reads < 32  # One binary search, not a set of 100,000 integers.


def test_acl_filtered_bm25_topk_against_direct_mathematics(tmp_path):
    documents = []
    for length in range(5):
        for words in itertools.product(("a", "b"), repeat=length):
            ident = f"{len(documents):02}"
            acl = frozenset(
                [{0: "*", 1: "user:alice", 2: "group:ops", 3: "user:hidden"}[int(ident) % 4]]
            )
            documents.append(
                Document(
                    ident, ident, " ".join(words), acl, {"type": "odd" if length % 2 else "even"}
                )
            )
    engine = Engine(tmp_path)
    engine.upsert_many("t", documents)
    engine.set_groups("t", "bob", ["ops"])
    queries = [(), ("a",), ("b",), ("a", "a"), ("a", "b"), ("b", "a", "b")]
    for subject, permissions in [
        ("alice", {"*", "user:alice"}),
        ("bob", {"*", "user:bob", "group:ops"}),
        ("stranger", {"*", "user:stranger"}),
    ]:
        for kind in (None, "odd", "even", "absent"):
            visible = [
                d
                for d in documents
                if d.acl & permissions and (kind is None or d.metadata["type"] == kind)
            ]
            words = {d.id: d.text.split() for d in visible}
            average = sum(map(len, words.values())) / len(visible) if visible else 0
            for phrase in queries:
                terms = sorted(set(phrase))
                frequency = {t: sum(t in ws for ws in words.values()) for t in terms}
                matches = [
                    d
                    for d in visible
                    if not phrase
                    or any(
                        tuple(words[d.id][i : i + len(phrase)]) == phrase
                        for i in range(len(words[d.id]) - len(phrase) + 1)
                    )
                ]
                expected = {}
                for document in matches:
                    parts = {}
                    for term in terms:
                        f = words[document.id].count(term)
                        idf = math.log((len(visible) + 1) / (frequency[term] + 0.5))
                        parts[term] = (
                            idf
                            * (f * 2.2)
                            / (f + 1.2 * (0.25 + 0.75 * len(words[document.id]) / average))
                        )
                    expected[document.id] = parts
                ordered = sorted(
                    expected, key=lambda ident: (-sum(expected[ident].values()), ident)
                )
                query = ('"' + " ".join(phrase) + '"') if phrase else ""
                if kind is not None:
                    query += " type:" + kind
                for limit, offset in [(1, 0), (3, 2), (100, 0)]:
                    result = engine.search(
                        Principal("t", subject), query, limit=limit, offset=offset
                    )
                    assert result.total == len(matches)
                    assert [hit.id for hit in result.hits] == ordered[offset : offset + limit]
                    assert result.visible_documents == len(visible)
                    assert result.statistics["document_frequency"] == frequency
                    assert result.statistics["average_length"] == average
                    assert result.facets == dict(Counter(d.metadata["type"] for d in matches))
                    for hit in result.hits:
                        assert hit.explanation == pytest.approx(expected[hit.id])
                        assert hit.score == pytest.approx(sum(expected[hit.id].values()))
