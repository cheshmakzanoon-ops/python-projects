"""Version-one deterministic command vocabulary. IDs identify logical effects."""

from dataclasses import dataclass
from typing import Literal

CommandKind = Literal[
    "ScheduleActivity", "StartTimer", "AwaitSignal", "Join", "Complete", "Fail", "Compensate"
]


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    command_id: str
    step: str = ""


@dataclass(frozen=True)
class ScheduleActivity(Command):
    kind: CommandKind = "ScheduleActivity"
    command_id: str = ""


@dataclass(frozen=True)
class StartTimer(Command):
    kind: CommandKind = "StartTimer"
    command_id: str = ""


@dataclass(frozen=True)
class AwaitSignal(Command):
    kind: CommandKind = "AwaitSignal"
    command_id: str = ""


@dataclass(frozen=True)
class Join(Command):
    kind: CommandKind = "Join"
    command_id: str = ""


@dataclass(frozen=True)
class Complete(Command):
    kind: CommandKind = "Complete"
    command_id: str = ""


@dataclass(frozen=True)
class Fail(Command):
    kind: CommandKind = "Fail"
    command_id: str = ""


@dataclass(frozen=True)
class Compensate(Command):
    kind: CommandKind = "Compensate"
    command_id: str = ""
