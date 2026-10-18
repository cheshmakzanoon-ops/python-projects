from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_current import Journal, Record


@given(
    st.lists(
        st.tuples(st.integers(0, 3), st.integers(0, 12), st.integers(-1, 1)),
        min_size=1,
        max_size=60,
    )
)
@settings(max_examples=35, deadline=None)
def test_admission_against_independent_first_commit_model(
    actions: list[tuple[int, int, int]],
) -> None:
    with TemporaryDirectory() as directory:
        journal = Journal(Path(directory) / "journal.db")
        model: dict[tuple[int, int], tuple[int, int]] = {}
        next_ordinal = 1
        for partition, offset, value in actions:
            key = partition, offset
            record = Record("s", partition, offset, value=value)
            prior = model.get(key)
            if prior is not None and prior[0] != value:
                import pytest

                with pytest.raises(ValueError):
                    journal.admit([record])
            else:
                assigned = journal.admit([record])[0].ingress_ordinal
                if prior is None:
                    model[key] = value, next_ordinal
                    next_ordinal += 1
                assert assigned == model[key][1]
        assert len(journal.read(0)) == len(model)
        journal.close()
