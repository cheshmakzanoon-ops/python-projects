from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pp_proving_ground.evaluation.metrics import (
    GatePolicy,
    asset_bootstrap,
    calibration,
    evaluate,
    metrics,
)
from pp_proving_ground.training.pipeline import fit, predict


def test_independent_metrics_and_calibration():
    labels = np.array([0, 0, 1, 1], dtype=np.int64)
    p = np.array([0.1, 0.4, 0.6, 0.9])
    report = metrics(labels, p)
    assert report["roc_auc"] == 1
    assert report["pr_auc"] == 1
    assert report["brier"] == pytest.approx((0.01 + 0.16 + 0.16 + 0.01) / 4)
    assert sum(b["count"] for b in calibration(labels, p)) == 4
    assert metrics(np.zeros(4, dtype=np.int64), p)["roc_auc"] is None
    for invalid in [np.array([np.nan] * 4), np.array([1.1] * 4), np.array([-0.1] * 4)]:
        with pytest.raises(ValueError):
            metrics(labels, invalid)


def test_asset_bootstrap_clusters_deterministic():
    y = np.array([0, 1, 0, 1, 0, 1], dtype=np.int64)
    p = np.array([0.1, 0.9, 0.2, 0.8, 0.3, 0.7])
    assets = np.array([1, 1, 2, 2, 3, 3], dtype=np.int64)
    report = asset_bootstrap(y, p, assets, 7, 50)
    assert report == asset_bootstrap(y, p, assets, 7, 50)
    assert report["unit"] == "asset"
    assert report["pr_auc_95_percentile"] == [1, 1]
    assert report["asset_count"] == 3


@pytest.mark.parametrize(
    "metric", ["pr_auc", "roc_auc", "brier", "count", "positives", "class_balance"]
)
@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_missing_nonfinite_metrics_fail(context, metric, value):
    report = replace(context.report, metrics={**context.report.metrics, metric: value})
    assert GatePolicy().judge(report)


@pytest.mark.parametrize(
    "metric,value",
    [
        ("pr_auc", 1.1),
        ("roc_auc", 1.1),
        ("brier", -0.1),
        ("class_balance", -0.1),
        ("class_balance", 1.1),
        ("class_balance", 0.5),
        ("count", 200.5),
        ("positives", 50.5),
        ("pr_auc", "0.8"),
    ],
)
def test_impossible_validation_metrics_are_ineligible(context, metric, value):
    values = {
        "count": 200,
        "positives": 50,
        "class_balance": 0.25,
        "pr_auc": 0.8,
        "roc_auc": 0.8,
        "brier": 0.1,
    }
    report = replace(context.report, metrics={**values, metric: value})
    assert GatePolicy().judge(report)


def test_one_class_validation_and_test_cannot_authorize(context):
    report = replace(
        context.report, metrics=metrics(np.zeros(200, dtype=np.int64), np.full(200, 0.2))
    )
    assert any("undefined" in r for r in GatePolicy().judge(report))
    assert GatePolicy().judge(replace(context.report, role="test"))
    insufficient = replace(
        context.report, metrics={**context.report.metrics, "count": 10, "positives": 5}
    )
    assert "insufficient validation samples/classes" in GatePolicy().judge(insufficient)


def test_prior_logistic_tree_and_final_test_separation(data, split, trained, context):
    policy = GatePolicy()
    initial = policy.identity
    prior = fit(data, split, "prior")
    assert policy.judge(evaluate(prior, data, split, "prior", bootstrap_repetitions=3))
    assert not policy.judge(context.report)
    tree = fit(data, split, "tree")
    assert np.isfinite(predict(tree.pipeline, data.features[:50])).all()
    final = evaluate(
        trained, data, split, context.manifest.identity, "test", bootstrap_repetitions=3
    )
    assert final.role == "test" and policy.judge(final)
    assert policy.identity == initial
    assert sum(b["count"] for b in final.calibration) == len(split.test)
    assert len(final.slices) == 6


def test_actual_one_class_validation_report_is_ineligible(data, split, trained):
    labels = data.labels.copy()
    labels[list(split.validation)] = 0
    changed = replace(data, labels=labels)
    new_split = replace(split, dataset_digest=changed.identity)
    report = evaluate(trained, changed, new_split, "one-class", bootstrap_repetitions=5)
    assert report.metrics["roc_auc"] is None
    assert report.metrics["pr_auc"] is None
    assert report.uncertainty["defined_repetitions"] == 0
    assert GatePolicy().judge(report)


def test_all_zero_and_all_one_trained_prior_prediction(data, split):
    for label in [0, 1]:
        labels = np.full(len(data.labels), label, dtype=np.int64)
        changed = replace(data, labels=labels)
        new_split = replace(split, dataset_digest=changed.identity)
        result = fit(changed, new_split, "prior")
        assert np.array_equal(predict(result.pipeline, data.features[:20]), np.full(20, label))
    with pytest.raises(ValueError):
        fit(data, split, "unsupported")
    with pytest.raises(ValueError):
        metrics(np.array([], dtype=np.int64), np.array([]))


def test_test_outcomes_do_not_change_training_validation_or_policy(data, split, trained):
    policy = GatePolicy()
    labels = data.labels.copy()
    labels[list(split.test)] = 1 - labels[list(split.test)]
    changed = replace(data, labels=labels)
    changed_split = replace(split, dataset_digest=changed.identity)
    second = fit(changed, changed_split, "logistic")
    before = evaluate(trained, data, split, "first", bootstrap_repetitions=3)
    after = evaluate(second, changed, changed_split, "second", bootstrap_repetitions=3)
    assert before.metrics == after.metrics
    assert policy.judge(before) == policy.judge(after)
    assert GatePolicy().identity == policy.identity
