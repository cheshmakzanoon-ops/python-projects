"""The exact fitted pipeline is reused by offline and serving inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from pp_proving_ground.data_contracts.schema import DatasetVersion, FloatArray
from pp_proving_ground.splits.manifest import SplitManifest

EstimatorName = Literal["prior", "logistic", "tree"]


@dataclass(frozen=True)
class TrainingResult:
    pipeline: Pipeline
    estimator: EstimatorName
    train_rows: int
    train_row_digest: str
    preprocessing: str = "median-impute-indicators+standard-scale-v1"


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
    if estimator == "prior":
        model: Any = DummyClassifier(strategy="prior")
    elif estimator == "logistic":
        model = LogisticRegression(max_iter=300, random_state=seed)
    elif estimator == "tree":
        model = DecisionTreeClassifier(max_depth=8, min_samples_leaf=20, random_state=seed)
    else:
        raise ValueError("unsupported estimator")
    # sklearn validates parameter names here; caller values deliberately override defaults.
    model.set_params(**params)
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
    return TrainingResult(pipeline, estimator, len(train), digest(data.row_ids[train].tolist()))


def predict(pipeline: Pipeline, features: FloatArray) -> FloatArray:
    if features.ndim != 2 or np.isinf(features).any():
        raise ValueError("expected bounded 2D finite-or-missing features")
    probabilities = np.asarray(pipeline.predict_proba(features), dtype=np.float64)
    classes = np.asarray(pipeline.classes_)
    matches = np.flatnonzero(classes == 1)
    if len(matches) == 0:
        return np.zeros(len(features), dtype=np.float64)
    return np.asarray(probabilities[:, int(matches[0])], dtype=np.float64)
