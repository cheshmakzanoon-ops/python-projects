from dataclasses import dataclass, field

from pp_anchor.definitions.model import JSON


@dataclass(frozen=True)
class HistoryEvent:
    seq: int
    kind: str
    step: str = ""
    data: JSON = field(default_factory=dict)
    commands: tuple[str, ...] = ()
