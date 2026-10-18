"""Portable diagnostics; columns are one-based Unicode code points."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Location:
    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class Evidence:
    line: int
    message: str


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: str
    confidence: str
    path: str
    location: Location
    sink_location: Location
    evidence: tuple[Evidence, ...]
    message: str
    coverage: str = "modeled"

    @property
    def identifier(self) -> str:
        key = (
            f"{self.rule_id}:{self.path}:{self.location.line}:{self.location.column}:{self.message}"
        )
        return hashlib.sha256(key.encode()).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.identifier, **asdict(self)}


def location(node: ast.AST, source: str) -> Location:
    lines = source.splitlines() or [""]
    start_line = getattr(node, "lineno", 1)
    end_line = getattr(node, "end_lineno", None) or start_line

    def column(line: int, byte: int) -> int:
        raw = lines[min(line, len(lines)) - 1].encode("utf-8")
        return len(raw[:byte].decode("utf-8", errors="ignore")) + 1

    return Location(
        start_line,
        column(start_line, getattr(node, "col_offset", 0)),
        end_line,
        column(end_line, getattr(node, "end_col_offset", 0) or 0),
    )
