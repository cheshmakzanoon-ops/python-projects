"""Type-reviewed estimator factory for the approved persisted model families."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.base import BaseEstimator
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier


class ProbabilisticModel(Protocol):
    classes_: NDArray[Any]

    def fit(self, features: NDArray[np.float64], labels: NDArray[np.int64]) -> Any: ...

    def predict_proba(self, features: NDArray[np.float64]) -> NDArray[np.float64]: ...


def build_estimator(
    name: str,
    *,
    seed: int,
    parameters: dict[str, Any] | None = None,
) -> BaseEstimator:
    """Whitelist supported estimators; never load arbitrary factories from config.

    Extending this list requires review of the persisted-type allowlist.
    """
    if name == "prior":
        model: BaseEstimator = DummyClassifier(strategy="prior")
    elif name == "logistic":
        model = LogisticRegression(max_iter=300, random_state=seed)
    elif name == "tree":
        model = DecisionTreeClassifier(max_depth=8, min_samples_leaf=20, random_state=seed)
    else:
        raise ValueError("unsupported estimator")
    model.set_params(**(parameters or {}))
    return model
