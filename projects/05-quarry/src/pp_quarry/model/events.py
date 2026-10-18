"""Format-v1 canonical event identity; identities include historical versions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TypeAlias

JSON: TypeAlias = str | int | float | bool | None | list["JSON"] | dict[str, "JSON"]


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


@dataclass(frozen=True)
class Event:
    namespace: str
    key: str
    version: int
    operation: str
    payload: dict[str, JSON]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.namespace, str)
            or not self.namespace
            or not self.key
            or not isinstance(self.key, str)
        ):
            raise ValueError("namespace and key must be nonempty strings")
        if type(self.version) is not int or self.version < 0:
            raise ValueError("version must be a nonnegative integer")
        if self.operation not in {"upsert", "delete"}:
            raise ValueError("operation must be upsert or delete")
        if self.operation == "delete" and self.payload:
            raise ValueError("delete payload must be empty")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        canonical(self.payload)

    @property
    def key_bytes(self) -> bytes:
        return canonical([self.namespace, self.key]).encode()

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            canonical(
                [self.namespace, self.key, self.version, self.operation, self.payload]
            ).encode()
        ).hexdigest()

    @classmethod
    def from_dict(cls, value: dict[str, JSON]) -> Event:
        namespace = value.get("source_namespace", value.get("namespace", "default"))
        key, version = value.get("key"), value.get("version")
        operation, payload = value.get("operation"), value.get("payload", {})
        if (
            not isinstance(namespace, str)
            or not isinstance(key, str)
            or type(version) is not int
            or not isinstance(operation, str)
            or not isinstance(payload, dict)
        ):
            raise ValueError(
                "invalid event fields: namespace/key strings, integer version, operation, object payload required"
            )
        return cls(namespace, key, version, operation, payload)
