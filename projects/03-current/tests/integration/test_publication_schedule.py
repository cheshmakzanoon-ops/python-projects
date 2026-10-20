"""Every durable publication boundary agrees with a separate full-history model."""

from dataclasses import replace
from pathlib import Path

import pytest

from pp_current import Config, Journal, Record, canonical
from tests.reference_trace import TraceModel


@pytest.mark.parametrize(
    "failure",
    [
        "checkpoint-before-stage",
        "checkpoint-during-stage",
        "checkpoint-before-publication",
        "checkpoint-after-publication",
    ],
)
@pytest.mark.parametrize("failed_cut", [0, 2])
def test_restarted_fault_schedule_preserves_all_revisions_and_the_processing_prefix(
    tmp_path: Path, failure: str, failed_cut: int
) -> None:
    config = Config(
        (canonical(["a", 0]), canonical(["b", 0])), size=10, slide=5, lateness=2, join_interval=3
    )
    trace = [
        Record("a", 0, 0, 1, "key", 3),
        Record("a", 0, 1, 10, kind="watermark"),
        Record("b", 0, 0, kind="idle"),
        Record("a", 0, 2, kind="end"),
        Record("b", 0, 1, kind="resume"),
        Record("b", 0, 2, 9, "key", 4),
        Record("b", 0, 3, 10, "key", stream="metadata", payload="equipment"),
        Record("b", 0, 4, 30, kind="watermark"),
        Record("b", 0, 5, 28, "key", 5),
        Record("b", 0, 6, kind="end"),
    ]
    model = TraceModel(config)
    expected: dict[tuple[str, str, str, int], str] = {}
    prefixes = {0: dict(expected)}
    for ordinal, record in enumerate(trace, 1):
        _, output = model.apply(replace(record, ingress_ordinal=ordinal))
        expected.update((delivery.identity, delivery.payload) for delivery in output)
        prefixes[ordinal] = dict(expected)
    path = tmp_path / "schedule.db"
    journal = Journal(path)
    try:
        journal.admit(trace)
    finally:
        journal.close()
    previous = 0

    def assert_prefix(journal: Journal, position: int) -> None:
        assert journal.recover(config, job_id="trace").position == position
        actual = {delivery.identity: delivery.payload for delivery in journal.pending()}
        assert actual == prefixes[position]
        assert len(journal.pending()) == len(actual)
        latest = {}
        for identity, payload in prefixes[position].items():
            logical = identity[:3]
            if logical not in latest or latest[logical][0] < identity[3]:
                latest[logical] = identity[3], payload
        rows = {
            (row["job_id"], row["operator_id"], row["logical_result_key"]): (
                row["revision"],
                canonical(row["payload"]),
            )
            for row in journal.export()
        }
        assert rows == latest

    for index, target in enumerate((2, 4, 7, 10)):
        journal = Journal(path)
        try:
            engine = journal.recover(config, job_id="trace")
            for record in journal.read(engine.position, target - engine.position):
                engine.apply(record)
            if index == failed_cut:

                def fail(point: str) -> None:
                    if point == failure:
                        raise OSError("publication boundary")

                journal.failpoint = fail
                with pytest.raises(OSError, match="boundary"):
                    journal.publish(engine)
                committed = target if failure == "checkpoint-after-publication" else previous
                assert_prefix(journal, committed)
                # The failed working state is discarded; recovery chooses the
                # committed prefix rather than guessing whether COMMIT happened.
                engine = journal.recover(config, job_id="trace")
                journal.failpoint = lambda _: None
                if engine.position < target:
                    for record in journal.read(engine.position, target - engine.position):
                        engine.apply(record)
            journal.publish(engine)
            assert_prefix(journal, target)
            previous = target
        finally:
            journal.close()
