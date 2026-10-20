"""Tiny exact arithmetic derives AP independently, including ties and absent classes."""

from fractions import Fraction
from itertools import product

import numpy as np
import pytest

from pp_proving_ground.evaluation.bootstrap import ClusteredAveragePrecision, asset_bootstrap


def exact_ap(rows):
    positives = sum(y for y, _ in rows)
    if positives in (0, len(rows)):
        return None
    # Direct definition: at each distinct threshold, count the included rows from scratch.
    answer = Fraction(0)
    for threshold in set(p for _, p in rows):
        included = [(y, p) for y, p in rows if p >= threshold]
        entering_positives = sum(y for y, p in rows if p == threshold)
        answer += Fraction(sum(y for y, _ in included), len(included)) * Fraction(
            entering_positives, positives
        )
    return float(answer)


@pytest.mark.parametrize("scores", [(0.2, 0.2, 0.8, 0.8, 0.5), (0.5,) * 5, (0, 1, 0.5, 1, 0)])
def test_all_tiny_cluster_draws_match_exact_threshold_definition(scores):
    labels = np.array([0, 1, 1, 0, 1], dtype=np.int64)
    assets = np.array([11, 11, -7, 20, 20], dtype=np.int64)
    plan = ClusteredAveragePrecision.prepare(labels, np.array(scores, dtype=np.float64), assets)
    units = sorted(set(assets.tolist()))
    for draw in product(range(3), repeat=3):
        rows = [
            (int(labels[i]), scores[i]) for a in draw for i in range(5) if assets[i] == units[a]
        ]
        expected = exact_ap(rows)
        actual = plan.estimate(np.bincount(draw, minlength=3))
        if expected is None:
            assert actual is None
        else:
            assert actual == pytest.approx(expected, abs=2e-15)


def test_seeded_resampling_matches_independent_expanded_fleets():
    labels = np.array([0, 1, 1, 0, 1], dtype=np.int64)
    probability = np.array([0.3, 0.3, 0.8, 0.8, 0.8])
    assets = np.array([1, 1, 7, 20, 20], dtype=np.int64)
    rng = np.random.default_rng(113)
    estimates = []
    for _ in range(97):
        draw = rng.choice(sorted(set(assets.tolist())), 3, replace=True)
        value = exact_ap(
            [(int(labels[i]), probability[i]) for a in draw for i in range(5) if a == assets[i]]
        )
        if value is not None:
            estimates.append(value)
    report = asset_bootstrap(labels, probability, assets, 113, 97)
    np.testing.assert_allclose(
        report["pr_auc_95_percentile"], np.quantile(estimates, [0.025, 0.975]), rtol=0, atol=2e-15
    )
    assert report["defined_repetitions"] == len(estimates)
    assert report["undefined_repetitions"] == 97 - len(estimates)
    assert report["undefined_repetitions"] > 0
    assert report["seed"] == 113


def test_bootstrap_sorts_scores_once_and_never_expands_draws(monkeypatch):
    import pp_proving_ground.evaluation.bootstrap as module

    count = 20000
    labels = np.arange(count, dtype=np.int64) % 2
    assets = np.arange(count, dtype=np.int64)
    probability = (np.arange(count, dtype=np.float64) % 97) / 97
    sizes = []

    class ObservedNumpy:
        def __getattr__(self, name):
            return getattr(np, name)

        def unique(self, values, **kwargs):
            sizes.append(len(values))
            return np.unique(values, **kwargs)

        def concatenate(self, *args, **kwargs):
            raise AssertionError("cluster resampling must not expand repeated rows")

    # Observe only this algorithm's calls; NumPy may concatenate its own small metadata.
    monkeypatch.setattr(module, "np", ObservedNumpy())
    report = asset_bootstrap(labels, probability, assets, 1729, 11)
    assert sizes == [count, count]
    assert report["defined_repetitions"] == 11
