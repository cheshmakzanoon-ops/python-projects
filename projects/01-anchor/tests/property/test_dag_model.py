"""Independent set oracle checks readiness and joins across generated DAG completions."""

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from pp_anchor import Definition, Step
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.reducer import WorkflowState, decide, replay


@given(
    st.integers(min_value=1, max_value=12),
    st.lists(st.integers(min_value=0, max_value=10000), min_size=12, max_size=12),
)
def test_ready_commands_equal_independent_predecessor_model(width, priorities):
    definition = Definition(
        "generated",
        1,
        tuple(Step(str(i)) for i in range(width))
        + (Step("join", kind="join", after=tuple(str(i) for i in range(width))),),
    )
    state = WorkflowState(definition)
    history = []
    event = HistoryEvent(1, "started", data={"digest": definition.digest})
    commands = decide(state, event)
    history.append(replace(event, commands=tuple(c.command_id for c in commands)))
    assert {c.step for c in commands} == {str(i) for i in range(width)}
    completed = set()
    for index in sorted(range(width), key=lambda i: (priorities[i], i)):
        completed.add(str(index))
        event = HistoryEvent(len(history) + 1, "step_completed", str(index))
        commands = decide(state, event)
        expected = {"step:join"} if len(completed) == width else set()
        assert {c.command_id for c in commands} == expected
        history.append(replace(event, commands=tuple(c.command_id for c in commands)))
    event = HistoryEvent(len(history) + 1, "step_completed", "join")
    commands = decide(state, event)
    history.append(replace(event, commands=tuple(c.command_id for c in commands)))
    assert replay(definition, history).done == completed | {"join"}
    assert replay(definition, history).status == "completed"
