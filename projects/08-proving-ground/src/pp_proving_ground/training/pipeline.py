"""The exact fitted pipeline is reused by offline and serving inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pp_proving_ground.data_contracts.schema import DatasetVersion, FloatArray
from pp_proving_ground.splits.manifest import SplitManifest
from pp_proving_ground.training.model_registry import build_estimator

EstimatorName = Literal["prior", "logistic", "tree"]
PREPROCESSING = "median-impute-indicators+standard-scale-v1"


@dataclass(frozen=True)
class TrainingResult:
    pipeline: Pipeline
    estimator: EstimatorName
    train_rows: int
    train_row_digest: str
    dataset_digest: str
    split_digest: str
    feature_names: tuple[str, ...]
    preprocessing: str = PREPROCESSING


def fit(
    data: DatasetVersion,
    split: SplitManifest,
    estimator: EstimatorName,
    seed: int = 1729,
    parameters: dict[str, Any] | None = None,
) -> TrainingResult:
    from pp_proving_ground.experiments.identity import digest

    split.validate(data)
    params = dict(parameters or {})
    model = build_estimator(estimator, seed=seed, parameters=params)
    pipeline = Pipeline(
        [
            (
                "imputer",
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            ),
            ("scaler", StandardScaler()),
            ("classifier", model),
        ]
    )
    train = split.indices("train")
    pipeline.fit(data.features[train], data.labels[train])
    return TrainingResult(
        pipeline,
        estimator,
        len(train),
        digest(data.row_ids[train].tolist()),
        data.identity,
        split.identity,
        tuple(feature.name for feature in data.schema),
    )


def predict(pipeline: Pipeline, features: FloatArray) -> FloatArray:
    if features.ndim != 2 or np.isinf(features).any():
        raise ValueError("expected bounded 2D finite-or-missing features")
    probabilities = np.asarray(pipeline.predict_proba(features), dtype=np.float64)
    classes = np.asarray(pipeline.classes_)
    if (
        classes.ndim != 1
        or len(classes) not in (1, 2)
        or len(np.unique(classes)) != len(classes)
        or not np.isin(classes, [0, 1]).all()
    ):
        raise ValueError("expected binary classifier classes")
    if (
        probabilities.shape != (len(features), len(classes))
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
        or not np.allclose(probabilities.sum(axis=1), 1.0, rtol=0, atol=1e-12)
    ):
        raise ValueError("invalid classifier probabilities")
    matches = np.flatnonzero(classes == 1)
    if len(matches) == 0:
        return np.zeros(len(features), dtype=np.float64)
    return np.asarray(probabilities[:, int(matches[0])], dtype=np.float64)
