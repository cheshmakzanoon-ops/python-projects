"""Validation gates are frozen independently of final-test judgments."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from pp_proving_ground.data_contracts.schema import DatasetVersion, FloatArray, IntArray
from pp_proving_ground.experiments.identity import digest
from pp_proving_ground.splits.manifest import SplitManifest
from pp_proving_ground.training.pipeline import TrainingResult, predict


@dataclass(frozen=True)
class EvaluationReport:
    artifact_digest: str
    dataset_digest: str
    split_digest: str
    role: Literal["validation", "test"]
    metrics: dict[str, float | int | None]
    calibration: tuple[dict[str, float | int | None], ...]
    slices: tuple[dict[str, Any], ...]
    uncertainty: dict[str, Any]
    version: int = 1

    @property
    def identity(self) -> str:
        return digest(asdict(self))


def metrics(labels: IntArray, probability: FloatArray) -> dict[str, float | int | None]:
    if len(labels) == 0 or len(labels) != len(probability):
        raise ValueError("empty/mismatched evaluation")
    if not np.isfinite(probability).all() or (probability < 0).any() or (probability > 1).any():
        raise ValueError("invalid probability")
    two_class = len(np.unique(labels)) == 2
    return {
        "count": len(labels),
        "positives": int(labels.sum()),
        "class_balance": float(labels.mean()),
        "pr_auc": float(average_precision_score(labels, probability)) if two_class else None,
        "roc_auc": float(roc_auc_score(labels, probability)) if two_class else None,
        "brier": float(brier_score_loss(labels, probability)),
    }


def calibration(
    labels: IntArray, probability: FloatArray
) -> tuple[dict[str, float | int | None], ...]:
    result: list[dict[str, float | int | None]] = []
    bins = np.minimum((probability * 10).astype(int), 9)
    for i in range(10):
        mask = bins == i
        result.append(
            {
                "lower": i / 10,
                "upper": (i + 1) / 10,
                "count": int(mask.sum()),
                "mean_prediction": float(probability[mask].mean()) if mask.any() else None,
                "observed_rate": float(labels[mask].mean()) if mask.any() else None,
            }
        )
    return tuple(result)


def asset_bootstrap(
    labels: IntArray, probability: FloatArray, assets: IntArray, seed: int, repetitions: int = 100
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    units = np.unique(assets)
    positions = {int(a): np.flatnonzero(assets == a) for a in units}
    estimates: list[float] = []
    for _ in range(repetitions):
        sampled = rng.choice(units, len(units), replace=True)
        indices = np.concatenate([positions[int(a)] for a in sampled])
        if len(np.unique(labels[indices])) == 2:
            estimates.append(float(average_precision_score(labels[indices], probability[indices])))
    interval = np.quantile(estimates, [0.025, 0.975]).tolist() if estimates else [None, None]
    return {
        "unit": "asset",
        "asset_count": len(units),
        "repetitions": repetitions,
        "defined_repetitions": len(estimates),
        "pr_auc_95_percentile": interval,
        "warning": "Descriptive clustered interval; small slices and one fleet limit inference.",
    }


def evaluate(
    result: TrainingResult,
    data: DatasetVersion,
    split: SplitManifest,
    artifact: str,
    role: Literal["validation", "test"] = "validation",
    seed: int = 1729,
    bootstrap_repetitions: int = 100,
) -> EvaluationReport:
    split.validate(data)
    indices = split.indices(role)
    labels = data.labels[indices]
    probability = predict(result.pipeline, data.features[indices])
    slices: list[dict[str, Any]] = []
    # Asset buckets defined before outcome inspection, plus missingness slices.
    for name, mask in [(f"asset_mod4={i}", data.assets[indices] % 4 == i) for i in range(4)] + [
        ("missing_sensor", np.isnan(data.features[indices]).any(axis=1)),
        ("complete_sensor", ~np.isnan(data.features[indices]).any(axis=1)),
    ]:
        slices.append(
            {
                "name": name,
                "metrics": metrics(labels[mask], probability[mask]) if mask.any() else {"count": 0},
                "insufficient": int(mask.sum()) < 100,
            }
        )
    return EvaluationReport(
        artifact,
        data.identity,
        split.identity,
        role,
        metrics(labels, probability),
        calibration(labels, probability),
        tuple(slices),
        asset_bootstrap(labels, probability, data.assets[indices], seed, bootstrap_repetitions),
    )


@dataclass(frozen=True)
class GatePolicy:
    version: str = "validation-v1"
    minimum_count: int = 100
    minimum_per_class: int = 10
    minimum_pr_auc: float = 0.35
    minimum_roc_auc: float = 0.65
    maximum_brier: float = 0.20

    @property
    def identity(self) -> str:
        return digest(asdict(self))

    def judge(self, report: EvaluationReport) -> tuple[str, ...]:
        failures: list[str] = []
        if report.version != 1 or report.role != "validation":
            failures.append("only schema-v1 validation reports can authorize promotion")
        for name in ["count", "positives", "class_balance", "pr_auc", "roc_auc", "brier"]:
            value = report.metrics.get(name)
            if value is None or isinstance(value, bool) or not math.isfinite(value):
                failures.append(f"{name}: missing, undefined or nonfinite")
        if failures:
            return tuple(failures)
        count = float(report.metrics["count"] or 0)
        positives = float(report.metrics["positives"] or 0)
        if count < self.minimum_count or min(positives, count - positives) < self.minimum_per_class:
            failures.append("insufficient validation samples/classes")
        for metric, threshold in [
            ("pr_auc", self.minimum_pr_auc),
            ("roc_auc", self.minimum_roc_auc),
        ]:
            if float(report.metrics[metric] or 0) < threshold:
                failures.append(f"{metric} below {threshold}")
        if float(report.metrics["brier"] or 0) > self.maximum_brier:
            failures.append(f"brier exceeds {self.maximum_brier}")
        return tuple(failures)
