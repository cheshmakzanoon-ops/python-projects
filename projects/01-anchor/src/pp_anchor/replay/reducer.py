"""Deterministic forward frontier and dependency-aware compensation state."""

from dataclasses import dataclass, field

from pp_anchor.definitions.commands import Command, CommandKind
from pp_anchor.definitions.model import Definition
from pp_anchor.history.events import HistoryEvent
from pp_anchor.replay.graph import WorkflowGraph

CURRENT_EVENT_VERSION = 2
EVENT_KINDS = frozenset(
    {
        "started",
        "signal",
        "activity_claimed",
        "step_completed",
        "step_failed",
        "retry_scheduled",
        "cancelled",
        "compensation_failed",
        "compensation_retry",
        "compensation_completed",
    }
)
KINDS: dict[str, CommandKind] = {
    "activity": "ScheduleActivity",
    "timer": "StartTimer",
    "signal": "AwaitSignal",
    "join": "Join",
}


class DivergenceError(ValueError):
    pass


@dataclass
class WorkflowState:
    definition: Definition
    status: str = "running"
    done: set[str] = field(default_factory=set)
    scheduled: set[str] = field(default_factory=set)
    compensation: dict[str, str] = field(default_factory=dict)
    signals: set[str] = field(default_factory=set)
    seq: int = 0
    history_schema_version: int = CURRENT_EVENT_VERSION
    graph: WorkflowGraph = field(init=False, repr=False)
    ready: set[str] = field(init=False, repr=False)
    remaining: dict[str, int] = field(init=False, repr=False)
    rollback_after: dict[str, frozenset[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.graph = WorkflowGraph(self.definition)
        self.remaining = {step.name: len(step.after) for step in self.definition.steps}
        self.ready = {name for name, count in self.remaining.items() if count == 0}

    def rollback_ready(self) -> set[str]:
        return {
            name
            for name, phase in self.compensation.items()
            if phase in ("pending", "blocked")
            and all(self.compensation[child] == "completed" for child in self.rollback_after[name])
        }

    def refresh_rollback(self) -> None:
        if self.history_schema_version >= 2:
            eligible = self.rollback_ready()
            for name, phase in self.compensation.items():
                if phase in ("pending", "blocked"):
                    self.compensation[name] = "pending" if name in eligible else "blocked"


def _validate_transition(state: WorkflowState, event: HistoryEvent) -> None:
    def reject(reason: str) -> None:
        raise DivergenceError(f"event {event.seq}: {reason}")

    if event.kind not in EVENT_KINDS:
        reject(f"unknown event kind {event.kind!r}")
    if (state.seq == 0) != (event.kind == "started"):
        reject("history must begin with exactly one started event")
    if event.kind == "started":
        return
    if state.status in ("completed", "failed", "compensated"):
        reject(f"transition after terminal state {state.status}")
    if event.kind in ("signal", "cancelled"):
        if state.status != "running" or event.step:
            reject("signal/cancellation requires a running workflow")
        if event.kind == "signal" and not isinstance(event.data.get("name"), str):
            reject("signal event has no name")
        return
    if event.step not in state.scheduled:
        reject(f"step {event.step!r} was never scheduled")
    if event.kind.startswith("compensation_"):
        if state.status != "compensating" or event.step not in state.compensation:
            reject("compensation event has no scheduled cleanup")
        phase = state.compensation[event.step]
        allowed = ("pending", "failed") if event.kind == "compensation_retry" else ("pending",)
        if phase not in allowed:
            reject(f"cleanup {event.step!r} is {phase}")
        return
    if event.kind == "activity_claimed":
        compensation = event.data.get("command_id") == f"compensate:{event.step}"
        if compensation:
            if state.status != "compensating" or event.step not in state.rollback_ready():
                reject("claimed cleanup is blocked by a descendant")
        elif (
            state.status != "running"
            or event.step in state.done
            or state.graph.steps[event.step].kind != "activity"
            or event.data.get("command_id") != f"step:{event.step}"
        ):
            reject("invalid activity claim")
        return
    if state.status != "running" or event.step in state.done:
        reject("ordinary transition requires an unfinished running step")
    if (
        event.kind in ("step_failed", "retry_scheduled")
        and state.graph.steps[event.step].kind != "activity"
    ):
        reject("only an activity can fail or retry")


def decide(state: WorkflowState, event: HistoryEvent) -> list[Command]:
    if event.seq != state.seq + 1:
        raise DivergenceError(f"event {event.seq}: non-monotonic sequence after {state.seq}")
    if event.schema_version not in (1, CURRENT_EVENT_VERSION):
        raise DivergenceError(
            f"event {event.seq}: unsupported history version {event.schema_version}"
        )
    if event.schema_version != state.history_schema_version:
        raise DivergenceError(f"event {event.seq}: mixed history versions")
    # Version one retains its historical acceptance rules and command stream.
    # New histories enforce legal state transitions as well as command identity.
    if state.history_schema_version >= 2:
        _validate_transition(state, event)
    if event.kind == "started" and event.data.get("digest") != state.definition.digest:
        raise DivergenceError(f"event {event.seq}: pinned definition digest mismatch")
    state.seq = event.seq
    if event.kind == "signal":
        state.signals.add(str(event.data["name"]))
    if event.kind == "step_completed":
        if event.step not in state.done:
            for successor in state.graph.successors.get(event.step, ()):
                state.remaining[successor] -= 1
                if state.remaining[successor] == 0:
                    state.ready.add(successor)
        state.done.add(event.step)
    if event.kind in ("cancelled", "step_failed"):
        if state.status in ("completed", "compensated", "failed"):
            return []
        state.status = "compensating"
        commands: list[Command] = []
        for step in reversed(state.definition.steps):
            if step.name in state.scheduled and step.compensate:
                state.compensation[step.name] = "pending"
                commands.append(Command("Compensate", f"compensate:{step.name}", step.name))
        state.rollback_after = state.graph.rollback_dependencies(set(state.compensation))
        state.refresh_rollback()
        if not commands:
            state.status = "failed"
            return [Command("Fail", "terminal:failed")]
        return commands
    if event.kind == "compensation_failed":
        state.compensation[event.step] = "failed"
    if event.kind == "compensation_retry":
        state.compensation[event.step] = "pending"
    if event.kind == "compensation_completed":
        state.compensation[event.step] = "completed"
        if all(v == "completed" for v in state.compensation.values()):
            state.status = "compensated"
            return [Command("Fail", "terminal:compensated")]
    if state.status != "running":
        state.refresh_rollback()
        return []
    commands = []
    for name in sorted(state.ready, key=state.graph.order.__getitem__):
        if name in state.scheduled:
            continue
        state.scheduled.add(name)
        step = state.graph.steps[name]
        commands.append(Command(KINDS[step.kind], f"step:{name}", name))
    state.ready.clear()
    if len(state.done) == len(state.definition.steps):
        state.status = "completed"
        commands.append(Command("Complete", "terminal:completed"))
    return commands


def replay(definition: Definition, events: list[HistoryEvent]) -> WorkflowState:
    version = events[0].schema_version if events else CURRENT_EVENT_VERSION
    state = WorkflowState(definition, history_schema_version=version)
    for event in events:
        commands = decide(state, event)
        actual = tuple(c.command_id for c in commands)
        if actual != event.commands:
            raise DivergenceError(
                f"event {event.seq}: expected commands {event.commands!r}, replay produced {actual!r}"
            )
    return state
