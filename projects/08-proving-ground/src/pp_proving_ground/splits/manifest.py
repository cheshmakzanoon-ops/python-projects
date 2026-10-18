"""Frozen memberships answer either future forecasting or unseen-asset generalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from pp_proving_ground.data_contracts.schema import ContractError, DatasetVersion, IntArray
from pp_proving_ground.experiments.identity import digest


@dataclass(frozen=True)
class SplitManifest:
    dataset_digest: str
    policy: Literal["temporal", "entity"]
    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]
    validation_boundary: float
    test_boundary: float
    embargo_hours: float
    question: str
    version: int = 1

    @property
    def identity(self) -> str:
        from dataclasses import asdict

        return digest(asdict(self))

    def indices(self, role: str) -> IntArray:
        if role not in {"train", "validation", "test"}:
            raise ContractError("unknown split role")
        values = getattr(self, role)
        if any(type(i) is not int for i in values):
            raise ContractError("split memberships must be exact integer indices")
        return np.array(values, dtype=np.int64)

    def validate(self, data: DatasetVersion) -> None:
        data.validate_availability()
        if self.version != 1 or self.dataset_digest != data.identity:
            raise ContractError("incompatible split manifest")
        if (
            self.policy not in {"temporal", "entity"}
            or self.embargo_hours < 0
            or not all(
                np.isfinite(v)
                for v in (self.embargo_hours, self.validation_boundary, self.test_boundary)
            )
        ):
            raise ContractError("unsupported split policy")
        parts = [self.train, self.validation, self.test]
        flattened = [i for part in parts for i in part]
        if any(type(i) is not int for i in flattened):
            raise ContractError("split memberships must be exact integer indices")
        if any(not part for part in parts) or len(set(flattened)) != len(flattened):
            raise ContractError("empty or overlapping split membership")
        if min(flattened) < 0 or max(flattened) >= len(data.labels):
            raise ContractError("out of bounds membership")
        if self.policy == "entity":
            groups = [set(data.assets[list(part)].tolist()) for part in parts]
            if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
                raise ContractError("entity holdout overlap")
        else:
            train, valid, test = (self.indices(r) for r in ("train", "validation", "test"))
            if not self.validation_boundary < self.test_boundary:
                raise ContractError("temporal boundaries")
            if (data.label_available_at[train] >= self.validation_boundary).any():
                raise ContractError("training label crosses validation boundary; purge required")
            if (data.observed_at[valid] < self.validation_boundary + self.embargo_hours).any():
                raise ContractError("validation embargo violated")
            if (data.label_available_at[valid] >= self.test_boundary).any():
                raise ContractError("validation label crosses test boundary; purge required")
            if (data.observed_at[test] < self.test_boundary + self.embargo_hours).any():
                raise ContractError("test embargo violated")


def freeze(
    data: DatasetVersion,
    policy: Literal["temporal", "entity"] = "temporal",
    embargo_hours: float = 2.0,
) -> SplitManifest:
    data.validate_availability()
    v, t = (float(x) for x in np.quantile(data.observed_at, [0.6, 0.8]))
    if policy == "temporal":
        train = np.flatnonzero(data.label_available_at < v)
        valid = np.flatnonzero(
            (data.observed_at >= v + embargo_hours) & (data.label_available_at < t)
        )
        test = np.flatnonzero(data.observed_at >= t + embargo_hours)
        question = "Forecast future observations of an existing asset fleet; assets may overlap."
    elif policy == "entity":
        entities = np.unique(data.assets)
        # Multiplicative hash ranks IDs without consulting outcomes.
        ordered = sorted(entities.tolist(), key=lambda a: digest({"asset": a, "salt": "entity-v1"}))
        a, b = int(len(ordered) * 0.6), int(len(ordered) * 0.8)
        train = np.flatnonzero(np.isin(data.assets, ordered[:a]))
        valid = np.flatnonzero(np.isin(data.assets, ordered[a:b]))
        test = np.flatnonzero(np.isin(data.assets, ordered[b:]))
        question = "Generalize to unseen assets; this is not a future forecasting estimate."
    else:
        raise ContractError("unsupported split policy")
    result = SplitManifest(
        data.identity,
        policy,
        tuple(train.tolist()),
        tuple(valid.tolist()),
        tuple(test.tolist()),
        v,
        t,
        embargo_hours,
        question,
    )
    result.validate(data)
    return result
