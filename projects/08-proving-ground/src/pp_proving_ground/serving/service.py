"""Capture one immutable serving snapshot per request, including response metadata."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from sklearn.pipeline import Pipeline

from pp_proving_ground.artifacts.store import ArtifactManifest
from pp_proving_ground.data_contracts.schema import FloatArray
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


class ServingProcess:
    def __init__(
        self,
        registry: Registry,
        loader: Callable[[str], tuple[Pipeline, ArtifactManifest]] | None = None,
    ):
        self.registry = registry
        self._loader = loader or registry.store.load
        self._snapshot: ServingSnapshot | None = None
        self._lock = threading.Lock()
        self._last_error: tuple[int, str] | None = None

    def refresh(self) -> bool:
        requested = self.registry.current()
        if requested.model_version is None or requested.artifact_digest is None:
            return False
        with self._lock:
            if (
                self._snapshot is not None
                and self._snapshot.applied_generation == requested.generation
            ):
                return True
        try:
            pipeline, manifest = self._loader(requested.artifact_digest)
            if manifest.identity != requested.artifact_digest:
                raise ValueError("loader returned different artifact")
            # Fail a malformed pipeline before it can become the active snapshot.
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
        except Exception as error:
            with self._lock:
                if self.registry.current().generation == requested.generation:
                    self._last_error = (requested.generation, str(error))
            return False
        with self._lock:
            # Checking both authoritative requested generation and applied generation prevents
            # old completed loads from moving serving state backwards.
            if self.registry.current() != requested:
                return False
            if (
                self._snapshot is not None
                and self._snapshot.applied_generation > requested.generation
            ):
                return False
            self._snapshot = candidate
            self._last_error = None
            return True

    def snapshot(self) -> ServingSnapshot:
        with self._lock:
            if self._snapshot is None:
                raise Unavailable("no successfully loaded model")
            return self._snapshot

    def readiness(self) -> dict[str, Any]:
        requested = self.registry.current()
        with self._lock:
            applied = self._snapshot.applied_generation if self._snapshot is not None else None
            error = (
                self._last_error[1]
                if self._last_error is not None and self._last_error[0] == requested.generation
                else None
            )
            return {
                "ready": applied == requested.generation and applied is not None,
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
        if not 1 <= len(records) <= 1000:
            raise ValueError("prediction requires 1..1000 records")
        names = snapshot.feature_names
        if any(set(row) != set(names) for row in records):
            raise ValueError("schema: exact feature names required")
        matrix = np.asarray(
            [[np.nan if row[n] is None else row[n] for n in names] for row in records],
            dtype=np.float64,
        )
        if np.isinf(matrix).any():
            raise ValueError("infinite input")
        # Do not recapture self._snapshot here: a swap after parsing must not change metadata.
        values = predict(snapshot.pipeline, matrix)
        return Prediction(
            tuple(values.tolist()),
            snapshot.artifact_digest,
            snapshot.model_version,
            snapshot.applied_generation,
        )
