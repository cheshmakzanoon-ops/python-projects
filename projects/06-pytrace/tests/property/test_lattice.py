from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.analysis.lattice import Value
from pp_pytrace.frontend.discovery import parse

values = st.builds(
    Value,
    taint=st.integers(0, 3),
    built=st.booleans(),
    unknown=st.booleans(),
    targets=st.frozensets(
        st.sampled_from(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]), max_size=8
    ),
    origins=st.frozensets(st.integers(1, 15), max_size=8),
)


@given(values, values, values)
def test_join_laws(left: Value, middle: Value, right: Value) -> None:
    assert left.join(left) == left
    assert left.join(middle) == middle.join(left)
    assert left.join(middle).join(right) == left.join(middle.join(right))
    assert left.join(middle).taint | left.taint == left.join(middle).taint


@settings(deadline=None, max_examples=50)
@given(st.lists(st.booleans(), min_size=1, max_size=8))
def test_branch_oracle_is_independent_boolean_model(sources: list[bool]) -> None:
    assignments = [
        " if flag_" + str(i) + ":\n  value=" + ("input()" if source else '"fixed"')
        for i, source in enumerate(sources)
    ]
    source = (
        'import os\ndef service():\n value="fixed"\n'
        + "\n".join(assignments)
        + "\n os.system(value)\n"
    )
    result = Analyzer(source, "property.py").run(parse(source))
    actual = any(item.rule_id == "PT001" for item in result.diagnostics)
    assert actual == any(sources)
