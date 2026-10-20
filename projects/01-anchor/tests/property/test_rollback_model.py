"""Independent transitive-ancestor oracle for forward and reverse DAG frontiers."""

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_anchor import Definition, Step
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.reducer import WorkflowState, decide, replay


@settings(max_examples=60, deadline=None)
@given(
    st.integers(min_value=1, max_value=12),
    st.lists(st.integers(min_value=0, max_value=4095), min_size=12, max_size=12),
    st.lists(st.integers(min_value=0, max_value=1000), min_size=12, max_size=12),
)
def test_reverse_frontier_matches_transitive_resource_dependencies(width, masks, priorities):
    names = [f"s{i}" for i in range(width)]
    predecessors = {
        name: {names[j] for j in range(i) if masks[i] & (1 << j)} for i, name in enumerate(names)
    }
    ancestors = {}
    for name in names:
        ancestors[name] = set(predecessors[name])
        for parent in predecessors[name]:
            ancestors[name].update(ancestors[parent])
    definition = Definition(
        "generated-rollback",
        1,
        tuple(
            Step(name, after=tuple(sorted(predecessors[name])), compensate="undo") for name in names
        )
        + (Step("hold", kind="signal", signal="hold", after=tuple(names)),),
    )
    state = WorkflowState(definition)
    history = []

    def record(kind, step="", data=None):
        event = HistoryEvent(len(history) + 1, kind, step, data or {})
        commands = decide(state, event)
        history.append(replace(event, commands=tuple(c.command_id for c in commands)))

    record("started", data={"digest": definition.digest})
    forward_done = set()
    while len(forward_done) < width:
        available = {
            name
            for name in names
            if name not in forward_done and predecessors[name] <= forward_done
        }
        assert available == (state.scheduled - state.done - {"hold"})
        name = min(available, key=lambda item: (priorities[names.index(item)], item))
        record("step_completed", name)
        forward_done.add(name)
    record("cancelled")
    undone = set()
    failed_once = False
    while len(undone) < width:
        expected = {
            name
            for name in names
            if name not in undone
            and not any(name in ancestors[other] for other in set(names) - undone)
        }
        assert {
            name for name, phase in state.compensation.items() if phase == "pending"
        } == expected
        name = min(expected, key=lambda item: (priorities[names.index(item)], item))
        if not failed_once:
            record("compensation_failed", name)
            assert state.status == "compensating"
            assert state.compensation[name] == "failed"
            record("compensation_retry", name)
            failed_once = True
        record("compensation_completed", name)
        undone.add(name)
    assert state.status == "compensated"
    reconstructed = replay(definition, history)
    assert reconstructed.compensation == state.compensation
    assert reconstructed.done == state.done == set(names)
