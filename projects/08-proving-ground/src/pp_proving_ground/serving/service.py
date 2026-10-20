"""Capture one immutable serving snapshot per request, including response metadata."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Callable

import numpy as np
from sklearn.pipeline import Pipeline

from pp_proving_ground.artifacts.store import ArtifactManifest
from pp_proving_ground.data_contracts.schema import FloatArray
from pp_proving_ground.evaluation.metrics import CURRENT_POLICY_VERSION
from pp_proving_ground.registry.sqlite import Registry
from pp_proving_ground.training.pipeline import predict


class Unavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ServingSnapshot:
    pipeline: Pipeline
    artifact_digest: str
    model_version: int
    applied_generation: int
    feature_names: tuple[str, ...]


@dataclass(frozen=True)
class Prediction:
    probabilities: tuple[float, ...]
    artifact_digest: str
    model_version: int
    applied_generation: int


@dataclass
class _LoadAttempt:
    complete: threading.Event = field(default_factory=threading.Event)
    applied: bool = False


class ServingProcess:
    def __init__(
        self,
        registry: Registry,
        loader: Callable[[str], tuple[Pipeline, ArtifactManifest]] | None = None,
    ):
        if registry.policy.version != CURRENT_POLICY_VERSION:
            raise ValueError("legacy registry is audit-only; re-evaluate before serving")
        self.registry = registry
        self._loader = loader or registry.store.load
        self._snapshot: ServingSnapshot | None = None
        self._lock = threading.Lock()
        self._last_error: tuple[int, str] | None = None
        self._inflight: dict[int, _LoadAttempt] = {}
        self._closed = False

    def refresh(self) -> bool:
        requested = self.registry.current()
        if requested.model_version is None or requested.artifact_digest is None:
            return False
        with self._lock:
            if self._closed:
                return False
            if (
                self._snapshot is not None
                and self._snapshot.applied_generation == requested.generation
            ):
                return True
            attempt = self._inflight.get(requested.generation)
            owner = attempt is None
            if attempt is None:
                attempt = _LoadAttempt()
                self._inflight[requested.generation] = attempt
        if not owner:
            # Coalesce concurrent retries of the same generation. A newer generation can
            # load independently, so a stuck old loader cannot block a rollback.
            attempt.complete.wait()
            with self._lock:
                return attempt.applied and not self._closed
        try:
            pipeline, manifest = self._loader(requested.artifact_digest)
            if manifest.identity != requested.artifact_digest:
                raise ValueError("loader returned different artifact")
            # Custom loaders must pass the same inference boundary as the normal store.
            probe = predict(pipeline, np.zeros((1, len(manifest.feature_names)), dtype=np.float64))
            if not np.isfinite(probe).all():
                raise ValueError("nonfinite probe prediction")
            candidate = ServingSnapshot(
                pipeline,
                requested.artifact_digest,
                requested.model_version,
                requested.generation,
                manifest.feature_names,
            )
            with self._lock:
                if self._closed or self.registry.current() != requested:
                    return False
                if (
                    self._snapshot is not None
                    and self._snapshot.applied_generation > requested.generation
                ):
                    return False
                self._snapshot = candidate
                self._last_error = None
                attempt.applied = True
                return True
        except Exception as error:
            with self._lock:
                if not self._closed and self.registry.current() == requested:
                    self._last_error = (requested.generation, str(error))
            return False
        finally:
            with self._lock:
                self._inflight.pop(requested.generation, None)
                attempt.complete.set()

    def close(self) -> None:
        """Stop accepting work; a captured prediction may finish, late loads cannot publish."""
        with self._lock:
            self._closed = True
            self._snapshot = None
            self._last_error = None
            for attempt in self._inflight.values():
                attempt.complete.set()

    def snapshot(self) -> ServingSnapshot:
        with self._lock:
            if self._closed:
                raise Unavailable("serving process is closed")
            if self._snapshot is None:
                raise Unavailable("no successfully loaded model")
            return self._snapshot

    def readiness(self) -> dict[str, Any]:
        with self._lock:
            # Read under the publication lock: a load cannot make applied exceed
            # an older requested generation captured before we acquired the lock.
            requested = self.registry.current()
            applied = self._snapshot.applied_generation if self._snapshot is not None else None
            error = (
                self._last_error[1]
                if self._last_error is not None and self._last_error[0] == requested.generation
                else None
            )
            return {
                "ready": not self._closed
                and applied == requested.generation
                and applied is not None,
                "closed": self._closed,
                "requested_generation": requested.generation,
                "applied_generation": applied,
                "model_version": self._snapshot.model_version if self._snapshot else None,
                "load_error": error,
            }

    def predict(self, features: FloatArray) -> Prediction:
        snapshot = self.snapshot()
        if (
            features.ndim != 2
            or features.shape[1] != len(snapshot.feature_names)
            or len(features) > 1000
            or len(features) < 1
        ):
            raise ValueError("prediction requires 1..1000 rows matching the feature schema")
        probabilities = predict(snapshot.pipeline, features)
        return Prediction(
            tuple(probabilities.tolist()),
            snapshot.artifact_digest,
            snapshot.model_version,
            snapshot.applied_generation,
        )

    def predict_records(self, records: list[dict[str, float | None]]) -> Prediction:
        snapshot = self.snapshot()
        if not isinstance(records, list) or not 1 <= len(records) <= 1000:
            raise ValueError("prediction requires 1..1000 records")
        names = snapshot.feature_names
        if any(not isinstance(row, dict) or set(row) != set(names) for row in records):
            raise ValueError("schema: exact feature names required")
        for row in records:
            for value in row.values():
                if value is None:
                    continue
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise ValueError("sensor values must be finite numbers or null")
                try:
                    finite = math.isfinite(value)
                except OverflowError as error:
                    raise ValueError("sensor value exceeds floating-point range") from error
                if not finite:
                    raise ValueError("sensor values must be finite numbers or null")
        matrix = np.asarray(
            [[np.nan if row[n] is None else row[n] for n in names] for row in records],
            dtype=np.float64,
        )
        # Do not recapture self._snapshot here: a swap after parsing must not change metadata.
        values = predict(snapshot.pipeline, matrix)
        return Prediction(
            tuple(values.tolist()),
            snapshot.artifact_digest,
            snapshot.model_version,
            snapshot.applied_generation,
        )
