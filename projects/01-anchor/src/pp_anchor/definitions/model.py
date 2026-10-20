"""Declarative DAG SDK: external effects never execute during replay."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Literal

JSON = dict[str, object]
MAX_JSON_DEPTH = 64


def validate_json(value: object) -> None:
    """Bound JSON structure and reject text PostgreSQL cannot represent.

    Iteration avoids recursion failures on untrusted values. Repeated container
    references are valid; cycles eventually exceed the depth bound.
    """
    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if isinstance(current, (dict, list, tuple)):
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting exceeds 64 levels")
            children = (
                [*current.keys(), *current.values()] if isinstance(current, dict) else current
            )
            pending.extend((child, depth + 1) for child in children)
        elif isinstance(current, str):
            if "\x00" in current:
                raise ValueError("JSON strings cannot contain null characters")
            try:
                current.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("JSON strings must contain valid Unicode") from exc


def canonical(value: object) -> str:
    validate_json(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Value must be finite JSON") from exc


def validate_activity_result(result: JSON | None) -> None:
    if result is not None and len(canonical(result).encode()) > 1_048_576:
        raise ValueError("Activity result exceeds 1 MiB")


@dataclass(frozen=True)
class Step:
    name: str
    activity: str = "identity"
    after: tuple[str, ...] = ()
    kind: Literal["activity", "timer", "signal", "join"] = "activity"
    delay: float = 0
    signal: str = ""
    compensate: str | None = None
    max_attempts: int = 3
    retry_delay: float = 0.02

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,100}", self.name):
            raise ValueError("Step name must be a bounded identifier")
        if not isinstance(self.activity, str) or not self.activity or len(self.activity) > 100:
            raise ValueError("Activity name must contain 1..100 characters")
        if not isinstance(self.after, tuple) or any(not isinstance(x, str) for x in self.after):
            raise ValueError("Dependencies must be a tuple of step names")
        if len(set(self.after)) != len(self.after):
            raise ValueError("Duplicate dependency")
        if self.compensate is not None and (
            not isinstance(self.compensate, str) or not 1 <= len(self.compensate) <= 100
        ):
            raise ValueError("Compensation name must contain 1..100 characters")
        if self.kind not in ("activity", "timer", "signal", "join"):
            raise ValueError("Unknown step kind")
        if (
            not isinstance(self.signal, str)
            or len(self.signal) > 100
            or (self.kind == "signal" and not self.signal)
        ):
            raise ValueError("Signal name required and at most 100 characters")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 32:
            raise ValueError("max_attempts must be an integer in 1..32")
        for number in (self.delay, self.retry_delay):
            if (
                type(number) not in (int, float)
                or not 0 <= number <= 31536000
                or not math.isfinite(number)
            ):
                raise ValueError("Delays must be finite seconds in 0..31536000")


@dataclass(frozen=True)
class Definition:
    name: str
    version: int
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 100:
            raise ValueError("Definition name must contain 1..100 characters")
        if type(self.version) is not int or not 1 <= self.version <= 2_147_483_647:
            raise ValueError("Definition version must be an integer in 1..2147483647")
        if (
            not isinstance(self.steps, tuple)
            or not 1 <= len(self.steps) <= 1000
            or any(not isinstance(s, Step) for s in self.steps)
        ):
            raise ValueError("Definition must contain 1..1000 steps")
        names = {s.name for s in self.steps}
        if len(names) != len(self.steps):
            raise ValueError("Definition needs unique named steps")
        seen: set[str] = set()
        for step in self.steps:
            if not set(step.after) <= seen:
                raise ValueError("Steps must be topologically ordered; dependencies must exist")
            seen.add(step.name)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical(self.to_dict()).encode()).hexdigest()

    def to_dict(self) -> JSON:
        return {
            "name": self.name,
            "version": self.version,
            "steps": [asdict(s) for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: JSON) -> "Definition":
        try:
            raw = data["steps"]
            if not isinstance(raw, list):
                raise ValueError("steps must be a list")
            steps: list[Step] = []
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError("step must be an object")
                item = dict(item)
                after = item.get("after", ())
                if not isinstance(after, (list, tuple)):
                    raise ValueError("after must be a list")
                item["after"] = tuple(after)
                steps.append(Step(**item))
            name, version = data["name"], data["version"]
            if not isinstance(name, str) or type(version) is not int:
                raise ValueError("Definition requires string name and integer version")
            return cls(name, version, tuple(steps))
        except (TypeError, KeyError) as exc:
            raise ValueError("Invalid definition fields") from exc
