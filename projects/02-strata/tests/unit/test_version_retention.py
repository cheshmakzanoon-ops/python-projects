from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_strata.codec.records import Record
from pp_strata.compaction import VersionRetention


@given(
    st.lists(
        st.dictionaries(
            st.binary(max_size=4), st.one_of(st.binary(max_size=8), st.none()), max_size=5
        ),
        min_size=1,
        max_size=40,
    ),
    st.data(),
)
@settings(max_examples=80, deadline=None)
def test_retention_preserves_every_view_above_floor_and_required_conflicts(batches, choices):
    history = [{}]
    records = []
    last_change = {}
    for sequence, writes in enumerate(batches, start=1):
        state = dict(history[-1])
        for key, value in writes.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
            last_change[key] = sequence
            records.append(Record(key, sequence, value))
        history.append(state)
    pinned = choices.draw(st.booleans())
    floor = choices.draw(st.integers(0, len(batches))) if pinned else len(batches)
    retention = VersionRetention(floor, pinned)
    kept = list(retention.records(sorted(records, key=lambda r: r.order)))
    for sequence in range(floor, len(batches) + 1):
        actual = {}
        for record in sorted(kept, key=lambda r: r.sequence):
            if record.sequence <= sequence:
                if record.value is None:
                    actual.pop(record.key, None)
                else:
                    actual[record.key] = record.value
        assert actual == history[sequence]
    assert retention.heads == {
        key: sequence
        for key, sequence in last_change.items()
        if key in history[-1] or sequence > floor
    }
