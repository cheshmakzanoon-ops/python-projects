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


class SourceMap:
    """Index source once; AST byte offsets convert to Unicode report columns."""

    def __init__(self, source: str) -> None:
        self.lines = tuple(line.encode("utf-8") for line in source.splitlines()) or (b"",)

    def location(self, node: ast.AST) -> Location:
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", None) or start_line

        def column(line: int, byte: int) -> int:
            raw = self.lines[min(line, len(self.lines)) - 1]
            return len(raw[:byte].decode("utf-8", errors="ignore")) + 1

        return Location(
            start_line,
            column(start_line, getattr(node, "col_offset", 0)),
            end_line,
            column(end_line, getattr(node, "end_col_offset", 0) or 0),
        )


def location(node: ast.AST, source: str) -> Location:
    """Convenience for single lookups; repeated callers should reuse SourceMap."""
    return SourceMap(source).location(node)
