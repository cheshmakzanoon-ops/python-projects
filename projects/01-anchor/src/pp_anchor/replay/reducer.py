"""Pure reducer. Only recorded events and the pinned definition influence commands."""

from dataclasses import dataclass, field

from pp_anchor.definitions.commands import Command, CommandKind
from pp_anchor.definitions.model import Definition
from pp_anchor.history.events import HistoryEvent


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


def decide(state: WorkflowState, event: HistoryEvent) -> list[Command]:
    if event.seq != state.seq + 1:
        raise DivergenceError(f"event {event.seq}: non-monotonic sequence after {state.seq}")
    state.seq = event.seq
    if event.kind == "started" and event.data.get("digest") != state.definition.digest:
        raise DivergenceError(f"event {event.seq}: pinned definition digest mismatch")
    if event.kind == "signal":
        state.signals.add(str(event.data["name"]))
    if event.kind == "step_completed":
        state.done.add(event.step)
    if event.kind in ("cancelled", "step_failed"):
        if state.status in ("completed", "compensated", "failed"):
            return []
        state.status = "compensating"
        commands: list[Command] = []
        # Include every scheduled effect: an in-flight activity may already have acted.
        for step in reversed(state.definition.steps):
            if step.name in state.scheduled and step.compensate:
                state.compensation[step.name] = "pending"
                commands.append(Command("Compensate", f"compensate:{step.name}", step.name))
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
        return []
    commands = []
    for step in state.definition.steps:
        if step.name in state.scheduled or not set(step.after) <= state.done:
            continue
        state.scheduled.add(step.name)
        kinds: dict[str, CommandKind] = {
            "activity": "ScheduleActivity",
            "timer": "StartTimer",
            "signal": "AwaitSignal",
            "join": "Join",
        }
        commands.append(Command(kinds[step.kind], f"step:{step.name}", step.name))
    if len(state.done) == len(state.definition.steps):
        state.status = "completed"
        commands.append(Command("Complete", "terminal:completed"))
    return commands


def replay(definition: Definition, events: list[HistoryEvent]) -> WorkflowState:
    state = WorkflowState(definition)
    for event in events:
        commands = decide(state, event)
        actual = tuple(c.command_id for c in commands)
        if actual != event.commands:
            raise DivergenceError(
                f"event {event.seq}: expected commands {event.commands!r}, replay produced {actual!r}"
            )
    return state
