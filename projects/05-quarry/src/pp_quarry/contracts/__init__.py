"""Explicit nullable-addition evolution and strict row contracts."""

from __future__ import annotations

import math
import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

from pp_quarry.model.events import JSON, Event


def _finite_bound(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in {int, float}:
        raise ValueError("quality bounds must be finite numbers")
    assert isinstance(value, (int, float))
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("quality bounds must be finite numbers") from exc
    if not math.isfinite(result):
        raise ValueError("quality bounds must be finite numbers")
    return result


@dataclass(frozen=True)
class Field:
    kind: str
    nullable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or type(self.nullable) is not bool:
            raise ValueError("field kind must be string and nullable must be boolean")


@dataclass(frozen=True)
class Contract:
    fields: Mapping[str, Field] = field(
        default_factory=lambda: {
            "device": Field("string"),
            "day": Field("string"),
            "value": Field("number"),
        }
    )
    minimum: float | None = None
    maximum: float | None = None
    min_rows: int = 0
    max_rows: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping) or any(
            not isinstance(spec, Field) for spec in self.fields.values()
        ):
            raise ValueError("contract fields must map names to Field definitions")
        # A frozen dataclass alone does not freeze a caller-owned dictionary.
        # Stage validation and publication must use the same schema snapshot.
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        if type(self.min_rows) is not int or (
            self.max_rows is not None and type(self.max_rows) is not int
        ):
            raise ValueError("dataset row bounds must be integers")
        if self.min_rows < 0 or (self.max_rows is not None and self.max_rows < self.min_rows):
            raise ValueError("invalid dataset row-count bounds")
        _finite_bound(self.minimum)
        _finite_bound(self.maximum)
        if any(not isinstance(name, str) or not name or "\x00" in name for name in self.fields):
            raise ValueError("contract field names must be nonempty strings without NUL bytes")
        if any(
            f.kind not in {"string", "number", "integer", "boolean", "json"}
            for f in self.fields.values()
        ):
            raise ValueError("unsupported contract field type")
        # DuckDB identifiers are ASCII case-insensitive, even when quoted. A
        # collision would silently rename a published payload__FIELD column.
        translation = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
        folded = [
            name.translate(translation)
            for name in self.fields
            if name not in {"device", "day", "value"}
        ]
        if len(set(folded)) != len(folded):
            raise ValueError("contract fields collide under SQL identifier case rules")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("invalid quality bounds")

    def compatible(self, old: Contract) -> None:
        for name, spec in old.fields.items():
            if name not in self.fields or self.fields[name] != spec:
                raise ValueError(
                    f"migration required: removed, renamed or incompatible field {name}"
                )
        for name, spec in self.fields.items():
            if name not in old.fields and not spec.nullable:
                raise ValueError(f"migration required: new column {name} must be nullable")

    def validate(self, event: Event) -> None:
        if event.operation == "delete":
            return
        unknown = set(event.payload) - self.fields.keys()
        if unknown:
            raise ValueError(f"undeclared columns: {sorted(unknown)}; declare nullable additions")
        for name, spec in self.fields.items():
            value: JSON = event.payload.get(name)
            if value is None:
                if not spec.nullable:
                    raise ValueError(f"{event.key}: required field {name}")
                continue
            valid = {
                "string": isinstance(value, str),
                "number": type(value) in {int, float},
                "integer": type(value) is int,
                "boolean": type(value) is bool,
                "json": True,
            }[spec.kind]
            if spec.kind == "integer" and isinstance(value, int) and not -(2**63) <= value < 2**63:
                raise ValueError(f"{event.key}: integer field {name} exceeds signed 64-bit format")
            if not valid or (type(value) is float and not math.isfinite(value)):
                raise ValueError(f"{event.key}: field {name} needs {spec.kind}")
            if spec.kind == "number" and isinstance(value, (int, float)):
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False
                if not finite:
                    raise ValueError(f"{event.key}: field {name} exceeds finite DOUBLE range")
        if event.payload.get("day") is not None:
            date.fromisoformat(str(event.payload["day"]))
        value = event.payload.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"{event.key}: value below minimum {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"{event.key}: value above maximum {self.maximum}")

    def to_dict(self) -> dict[str, JSON]:
        return {
            "fields": {k: {"kind": f.kind, "nullable": f.nullable} for k, f in self.fields.items()},
            "minimum": self.minimum,
            "maximum": self.maximum,
            "min_rows": self.min_rows,
            "max_rows": self.max_rows,
        }

    @classmethod
    def from_dict(cls, value: dict[str, JSON]) -> Contract:
        fields = value["fields"]
        if not isinstance(fields, dict):
            raise ValueError("invalid contract")
        specs: dict[str, Field] = {}
        for name, spec in fields.items():
            if not isinstance(spec, dict):
                raise ValueError("invalid field spec")
            kind, nullable = spec.get("kind"), spec.get("nullable")
            if not isinstance(kind, str) or type(nullable) is not bool:
                raise ValueError("invalid field spec: string kind and boolean nullable required")
            specs[name] = Field(kind, nullable)
        minimum = _finite_bound(value.get("minimum"))
        maximum = _finite_bound(value.get("maximum"))
        min_rows = value.get("min_rows", 0)
        max_rows = value.get("max_rows")
        if type(min_rows) is not int or (max_rows is not None and type(max_rows) is not int):
            raise ValueError("dataset row bounds must be integers")
        return cls(
            specs,
            minimum,
            maximum,
            min_rows if isinstance(min_rows, int) else 0,
            max_rows if isinstance(max_rows, int) else None,
        )
