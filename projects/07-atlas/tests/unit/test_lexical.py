import html
import math

import pytest

from pp_atlas import Document, Engine, Principal
from pp_atlas.ingest.tokenizer import tokenize
from pp_atlas.query import parse
from pp_atlas.ranking.bm25 import contribution
from pp_atlas.snippets import snippet


def test_at01_hand_scores_six_documents(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert_many(
        "a",
        [
            Document(str(i), str(i), text)
            for i, text in enumerate(["cat cat dog", "cat", "dog dog", "bird", "", "cat dog bird"])
        ],
    )
    principal = Principal("a", "reader")
    result = engine.search(principal, "cat")
    # N=6, df(cat)=3, total length=10, avg=5/3. Independent arithmetic.
    idf = math.log(2)
    expected = {
        "0": idf * 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 3 / (5 / 3))),
        "1": idf * 2.2 / (1 + 1.2 * (0.25 + 0.75 / (5 / 3))),
        "5": idf * 2.2 / (1 + 1.2 * (0.25 + 0.75 * 3 / (5 / 3))),
    }
    assert [h.id for h in result.hits] == sorted(expected, key=lambda d: (-expected[d], d))
    assert {h.id: h.score for h in result.hits} == pytest.approx(expected)
    assert engine.search(principal, "cat cat").hits == result.hits
    assert engine.search(principal, "").hits[0].id == "0"
    assert engine.search(Principal("empty", "r"), "cat").total == 0
    assert contribution(0, 0, 0, 0, 0) == 0
    with pytest.raises(ValueError):
        contribution(1, 1, 1, 1, 1, b=2)
    with pytest.raises(ValueError):
        contribution(1, 1, 1, 2, 1)


def test_at02_unicode_and_original_offsets():
    text = '<script>alert("x")</script> Straße CAFE\u0301 Ｆｏｏ ﬁsh 中文'
    tokens = tokenize(text)
    assert [t.term for t in tokens][-5:] == ["strasse", "café", "foo", "fish", "中文"]
    output = snippet(text, tokens, frozenset({"strasse", "café", "foo"}), 500)
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "<mark>Straße</mark>" in output
    assert "<mark>CAFE\u0301</mark>" in output
    assert "<mark>Ｆｏｏ</mark>" in output
    assert html.escape(text) == snippet(text, tokens, frozenset(), 500)
    assert tokenize("가")[0].term == tokenize("가")[0].term == tokenize("ㄱㅏ")[0].term
    assert snippet("가", tokenize("가"), frozenset({"가"})) == "<mark>가</mark>"


@pytest.mark.parametrize(
    "text",
    [
        '"open',
        '""',
        "x:thing",
        "tag:",
        r"a\b",
        "x " * 33,
        '"' + "x " * 17 + '"',
        "a" * 4097,
        " ".join("type:x" for _ in range(9)),
    ],
)
def test_at07_bounded_parser(text):
    with pytest.raises(ValueError):
        parse(text)


def test_at02_phrase_repetition_filter_and_tie(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert_many(
        "t",
        [
            Document("b", "B", "red red blue", metadata={"type": "runbook"}),
            Document("a", "A", "red blue red", metadata={"type": "design"}),
            Document("c", "C", "red red blue", metadata={"type": "runbook"}),
        ],
    )
    p = Principal("t", "r")
    assert [h.id for h in engine.search(p, '"red red"').hits] == ["b", "c"]
    assert [h.id for h in engine.search(p, "red type:design").hits] == ["a"]
    assert engine.search(p, "red type:runbook").visible_documents == 2
    assert engine.search(p, "missing").total == 0


def test_parameter_and_document_bounds(tmp_path):
    with pytest.raises(ValueError):
        Engine(tmp_path, k1=0)
    for args in [("", "", ""), ("x", "a" * 1025, "")]:
        with pytest.raises(ValueError):
            Document(*args)
    with pytest.raises(ValueError):
        Document("x", "", "", frozenset({""}))
    with pytest.raises(ValueError):
        tokenize("x" * 2_000_001)
    with pytest.raises(ValueError):
        Principal("", "x")
    engine = Engine(tmp_path)
    assert engine.upsert_many("t", []) == {}
    with pytest.raises(ValueError):
        engine.upsert_many("t", [Document("a", "", ""), Document("a", "", "")])
    with pytest.raises(ValueError):
        engine.search(Principal("t", "a"), "", limit=101)


@pytest.mark.parametrize("k1", [math.nan, math.inf, -math.inf])
def test_nonfinite_ranking_parameters_are_rejected(tmp_path, k1):
    with pytest.raises(ValueError):
        Engine(tmp_path, k1=k1)
    with pytest.raises(ValueError):
        contribution(1, 1, 1, 1, 1, k1=k1)
