"""Canonical semantic identities; timestamps belong to attempts, never run IDs."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class ExperimentSpec:
    dataset_digest: str
    split_digest: str
    code_digest: str
    preprocessing: str
    estimator: str
    parameters: dict[str, Any]
    seed: int
    lock_digest: str
    format_version: int = 1

    @property
    def identity(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class RunRecord:
    experiment_id: str
    attempt_id: str
    started_at: str
    environment: dict[str, str]
    format_version: int = 1

    @classmethod
    def begin(cls, spec: ExperimentSpec, root: Path, environment: dict[str, str]) -> RunRecord:
        run_root = root / spec.identity
        run_root.mkdir(parents=True, exist_ok=True)
        spec_path = run_root / "spec.json"
        encoded_spec = canonical(asdict(spec))
        if spec_path.exists():
            if spec_path.read_bytes() != encoded_spec:
                raise ValueError("stored experiment specification differs from semantic identity")
        else:
            atomic_json(spec_path, asdict(spec))
        record = cls(spec.identity, uuid.uuid4().hex, datetime.now(UTC).isoformat(), environment)
        atomic_json(root / spec.identity / f"{record.attempt_id}.json", asdict(record))
        return record
