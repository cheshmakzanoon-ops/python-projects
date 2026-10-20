from dataclasses import replace

import pytest

from pp_anchor import Definition, Step
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.reducer import DivergenceError, WorkflowState, decide, replay


def started(definition):
    state = WorkflowState(definition)
    event = HistoryEvent(1, "started", data={"digest": definition.digest})
    return state, replace(event, commands=tuple(c.command_id for c in decide(state, event)))


def test_completion_cannot_replace_an_unrelated_scheduled_step():
    definition = Definition("one", 1, (Step("only"),))
    state, first = started(definition)
    event = HistoryEvent(2, "step_completed", "never-scheduled", commands=("terminal:completed",))
    with pytest.raises(DivergenceError, match="event 2"):
        replay(definition, [first, event])
    assert state.done == set()


@pytest.mark.parametrize(
    "kind,step", [("mystery", ""), ("started", ""), ("compensation_completed", "only")]
)
def test_new_history_rejects_impossible_transition_kinds_and_phases(kind, step):
    definition = Definition("one", 1, (Step("only"),))
    state, _ = started(definition)
    with pytest.raises(DivergenceError, match="event 2"):
        decide(state, HistoryEvent(2, kind, step))
    assert state.seq == 1


def test_duplicate_completion_and_events_after_terminal_are_rejected():
    definition = Definition("two", 1, (Step("a"), Step("b", after=("a",))))
    state, _ = started(definition)
    decide(state, HistoryEvent(2, "step_completed", "a"))
    with pytest.raises(DivergenceError, match="unfinished"):
        decide(state, HistoryEvent(3, "step_completed", "a"))
    decide(state, HistoryEvent(3, "step_completed", "b"))
    with pytest.raises(DivergenceError, match="terminal"):
        decide(state, HistoryEvent(4, "cancelled"))


def test_legacy_history_retains_original_command_stream_and_version():
    definition = Definition(
        "legacy", 1, (Step("a", compensate="undo"), Step("b", after=("a",), compensate="undo"))
    )
    events = [
        HistoryEvent(
            1, "started", data={"digest": definition.digest}, commands=("step:a",), schema_version=1
        ),
        HistoryEvent(2, "step_completed", "a", commands=("step:b",), schema_version=1),
        HistoryEvent(3, "cancelled", commands=("compensate:b", "compensate:a"), schema_version=1),
        HistoryEvent(4, "compensation_completed", "a", schema_version=1),
        HistoryEvent(
            5, "compensation_completed", "b", commands=("terminal:compensated",), schema_version=1
        ),
    ]
    state = replay(definition, events)
    assert state.status == "compensated" and state.history_schema_version == 1
    with pytest.raises(DivergenceError, match="mixed"):
        replay(definition, [events[0], replace(events[1], schema_version=2)])


def test_cumulative_retry_batches_cap_without_numeric_overflow():
    from pp_anchor.persistence.engine import retry_delay

    assert retry_delay(0, 2000) == 0
    assert retry_delay(1, 2000) == 31536000
    assert 0 < retry_delay(1e-320, 1025) < 1
