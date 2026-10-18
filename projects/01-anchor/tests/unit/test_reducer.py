import itertools
from dataclasses import replace

import pytest

from pp_anchor import Definition, Step
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.reducer import DivergenceError, WorkflowState, decide, replay


def recorded(state, kind, step="", data=None):
    event = HistoryEvent(state.seq + 1, kind, step, data or {})
    return replace(event, commands=tuple(c.command_id for c in decide(state, event)))


def test_AN01_AN06_all_join_orders():
    definition = Definition(
        "parallel",
        1,
        (Step("a"), Step("b"), Step("c"), Step("joined", kind="join", after=("a", "b", "c"))),
    )
    for order in itertools.permutations(("a", "b", "c")):
        state = WorkflowState(definition)
        history = [recorded(state, "started", data={"digest": definition.digest})]
        assert history[0].commands == ("step:a", "step:b", "step:c")
        for name in order:
            history.append(recorded(state, "step_completed", name))
        assert history[-1].commands == ("step:joined",)
        history.append(recorded(state, "step_completed", "joined"))
        assert history[-1].commands == ("terminal:completed",)
        assert replay(definition, history).status == "completed"
        with pytest.raises(DivergenceError, match="event 1"):
            replay(replace(definition, version=2), history)
        with pytest.raises(DivergenceError, match="event 2"):
            replay(definition, [history[0], replace(history[1], commands=("unexpected",))])


@pytest.mark.parametrize(
    "steps",
    [
        (Step("x", after=("missing",)),),
        (Step("x"), Step("x")),
    ],
)
def test_invalid_definitions(steps):
    with pytest.raises(ValueError):
        Definition("bad", 1, steps)


def test_serialized_definition_stability():
    definition = Definition("stable", 1, (Step("x"),))
    assert Definition.from_dict(definition.to_dict()).digest == definition.digest
    with pytest.raises(DivergenceError, match="non-monotonic"):
        decide(WorkflowState(definition), HistoryEvent(2, "started"))


def test_compensation_includes_inflight_not_only_completed():
    definition = Definition("fence", 1, (Step("effect", compensate="cleanup"),))
    state = WorkflowState(definition)
    recorded(state, "started", data={"digest": definition.digest})
    event = recorded(state, "cancelled")
    assert event.commands == ("compensate:effect",)
    assert state.status == "compensating"
    recorded(state, "compensation_failed", "effect")
    assert state.compensation == {"effect": "failed"}
    assert state.status == "compensating"
    recorded(state, "compensation_retry", "effect")
    recorded(state, "compensation_completed", "effect")
    assert state.status == "compensated"
