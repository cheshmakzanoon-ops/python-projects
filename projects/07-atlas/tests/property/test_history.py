from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pp_atlas import Document, Engine, Principal


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["put", "delete", "acl", "merge"]), st.integers(0, 5), st.booleans()
        ),
        min_size=1,
        max_size=25,
    )
)
def test_catalog_history_matches_independent_ascii_model(tmp_path, operations):
    import tempfile

    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        engine = Engine(directory)
        model = {}
        p = Principal("t", "alice")
        for action, number, visible in operations:
            ident = str(number)
            if action == "put":
                engine.upsert(
                    "t",
                    Document(
                        ident,
                        ident,
                        "common red red" if number % 2 else "common blue",
                        frozenset({"*"} if visible else {"user:bob"}),
                    ),
                )
                model[ident] = (visible, number % 2 == 1)
            elif action == "delete":
                engine.delete("t", ident)
                model.pop(ident, None)
            elif action == "acl" and ident in model:
                engine.set_acl("t", ident, ["*"] if visible else ["user:bob"])
                model[ident] = (visible, model[ident][1])
            elif action == "merge":
                engine.merge("t")
            expected = {key for key, (allowed, red) in model.items() if allowed and red}
            result = engine.search(p, '"red red"', limit=100)
            assert {h.id for h in result.hits} == expected
            assert result.total == len(expected)
            assert {d.id for d in engine.export(p)} == {
                key for key, (allowed, _) in model.items() if allowed
            }


@settings(max_examples=100, deadline=None)
@given(st.text(alphabet=st.sampled_from(list("abc Ｆﬃßİé\u0301각ㄱㅏ가中文<&>")), max_size=40))
def test_normalization_equivalence_and_source_bounds(text):
    import unicodedata

    from pp_atlas.ingest.tokenizer import tokenize

    original = tokenize(text)
    normalized = tokenize(unicodedata.normalize("NFKC", text))
    assert [t.term for t in original] == [t.term for t in normalized]
    assert all(0 <= token.start < token.end <= len(text) for token in original)
    assert all(a.end <= b.start for a, b in zip(original, original[1:]))
