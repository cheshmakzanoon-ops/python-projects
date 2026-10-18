"""Preserve approved model families when extracting the trainer registry."""

import pytest
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from pp_proving_ground.training.model_registry import build_estimator


def test_built_in_families() -> None:
    assert isinstance(build_estimator("prior", seed=1), DummyClassifier)
    assert isinstance(build_estimator("logistic", seed=1), LogisticRegression)
    assert isinstance(build_estimator("tree", seed=1), DecisionTreeClassifier)


def test_unreviewed_estimator_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported estimator"):
        build_estimator("custom.UntrustedModel", seed=1)


def test_parameter_override() -> None:
    model = build_estimator("logistic", seed=1, parameters={"max_iter": 50})
    assert model.get_params()["max_iter"] == 50
