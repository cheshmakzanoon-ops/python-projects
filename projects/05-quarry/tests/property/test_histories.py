from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_quarry import Config, Lakehouse, Snapshot
from tests.conftest import event, source


@given(
    st.lists(
        st.tuples(st.integers(0, 5), st.integers(0, 30), st.booleans()), min_size=1, max_size=40
    )
)
@settings(max_examples=30, deadline=None)
def test_independent_highest_version_model(actions: list[tuple[int, int, bool]]) -> None:
    # Version payload is deterministic so retries and arbitrary arrival orders are valid.
    rows = [
        event(str(k), v, v * 3, operation="delete" if delete else "upsert")
        for k, v, delete in actions
    ]
    unique: dict[tuple[str, int], dict[str, object]] = {}
    for row in rows:
        unique.setdefault((row["key"], row["version"]), row)
    rows = list(unique.values())
    expected: dict[str, tuple[int, bool, int]] = {}
    for row in rows:
        key, version = row["key"], row["version"]
        if key not in expected or version > expected[key][0]:
            expected[key] = (version, row["operation"] == "delete", version * 3)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        with Lakehouse(path / "lake", Config(buckets=2)) as lake:
            mid = len(rows) // 2
            lake.ingest(source(path, rows[:mid], "a.ndjson"))
            lake.ingest(source(path, rows[mid:], "b.ndjson"))
            with Snapshot(lake.root) as handle:
                actual = {row["key"]: (row["version"], row["value"]) for row in handle.rows()}
            assert actual == {
                key: (version, value)
                for key, (version, deleted, value) in expected.items()
                if not deleted
            }
