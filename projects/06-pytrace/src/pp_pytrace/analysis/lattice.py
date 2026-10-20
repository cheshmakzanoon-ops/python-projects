"""Finite product lattice. Evidence is bounded metadata, never the convergence key."""

from __future__ import annotations

from dataclasses import dataclass

SHELL = 1
SQL = 2


@dataclass(frozen=True)
class Value:
    taint: int = 0
    built: bool = False
    unknown: bool = False
    targets: frozenset[str] = frozenset()
    origins: frozenset[int] = frozenset()
    sql_protocol: bool = False

    def __post_init__(self) -> None:
        if "*" in self.targets or len(self.targets) > 8:
            object.__setattr__(self, "targets", frozenset(["*"]))
            object.__setattr__(self, "unknown", True)
        if len(self.origins) > 8:
            object.__setattr__(self, "origins", frozenset(sorted(self.origins)[:8]))

    def join(self, other: Value) -> Value:
        targets = self.targets | other.targets
        if "*" in targets or len(targets) > 8:
            targets = frozenset(["*"])
        return Value(
            self.taint | other.taint,
            self.built or other.built,
            self.unknown or other.unknown or "*" in targets,
            targets,
            frozenset(sorted(self.origins | other.origins)[:8]),
            self.sql_protocol or other.sql_protocol,
        )

    @property
    def key(self) -> tuple[int, bool, bool, frozenset[str], bool]:
        return self.taint, self.built, self.unknown, self.targets, self.sql_protocol


UNKNOWN = Value(unknown=True)
BOTTOM = Value()
Environment = dict[str, Value]


def join_environments(left: Environment, right: Environment) -> Environment:
    return {
        key: left.get(key, UNKNOWN).join(right.get(key, UNKNOWN))
        for key in left.keys() | right.keys()
    }


def environment_key(
    env: Environment,
) -> tuple[tuple[str, tuple[int, bool, bool, frozenset[str], bool]], ...]:
    return tuple(sorted((key, value.key) for key, value in env.items()))
