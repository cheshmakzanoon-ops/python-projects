"""Asset-cluster resampling without expanding duplicate rows or repeatedly sorting scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pp_proving_ground.data_contracts.schema import FloatArray, IntArray


@dataclass(frozen=True)
class ClusteredAveragePrecision:
    """One fixed ordering of tied scores; each draw changes only asset multiplicities."""

    asset_index: IntArray
    score_index: IntArray
    positive_assets: IntArray
    positive_scores: IntArray
    asset_count: int
    score_count: int

    @classmethod
    def prepare(
        cls, labels: IntArray, probability: FloatArray, assets: IntArray
    ) -> ClusteredAveragePrecision:
        if (
            labels.ndim != 1
            or probability.ndim != 1
            or assets.ndim != 1
            or len(labels) == 0
            or not len(labels) == len(probability) == len(assets)
            or not np.isin(labels, [0, 1]).all()
            or not np.isfinite(probability).all()
            or (probability < 0).any()
            or (probability > 1).any()
        ):
            raise ValueError("expected nonempty binary labels, probabilities and asset IDs")
        units, asset_index = np.unique(assets, return_inverse=True)
        scores, score_index = np.unique(probability, return_inverse=True)
        # Rank 0 is the largest probability; all equal scores enter together.
        score_index = len(scores) - 1 - score_index
        positive = labels == 1
        return cls(
            asset_index,
            score_index,
            asset_index[positive],
            score_index[positive],
            len(units),
            len(scores),
        )

    def estimate(self, multiplicities: IntArray) -> float | None:
        totals = np.bincount(
            self.score_index, weights=multiplicities[self.asset_index], minlength=self.score_count
        )
        positives = np.bincount(
            self.positive_scores,
            weights=multiplicities[self.positive_assets],
            minlength=self.score_count,
        )
        positive_count, count = float(positives.sum()), float(totals.sum())
        if positive_count == 0 or positive_count == count:
            return None
        cumulative_count = totals.cumsum()
        precision = np.divide(
            positives.cumsum(),
            cumulative_count,
            out=np.zeros(self.score_count, dtype=np.float64),
            where=cumulative_count > 0,
        )
        # AP = sum over tied-score thresholds of precision * positive recall increment.
        return float(np.dot(precision, positives) / positive_count)


def asset_bootstrap(
    labels: IntArray, probability: FloatArray, assets: IntArray, seed: int, repetitions: int = 100
) -> dict[str, Any]:
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("bootstrap repetitions must be a positive integer")
    plan = ClusteredAveragePrecision.prepare(labels, probability, assets)
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sampled = rng.choice(plan.asset_count, plan.asset_count, replace=True)
        multiplicities = np.bincount(sampled, minlength=plan.asset_count)
        estimate = plan.estimate(multiplicities)
        if estimate is not None:
            estimates.append(estimate)
    interval = np.quantile(estimates, [0.025, 0.975]).tolist() if estimates else [None, None]
    return {
        "unit": "asset",
        "asset_count": plan.asset_count,
        "row_count": len(labels),
        "score_groups": plan.score_count,
        "algorithm": "cluster-multiplicity-tied-ap-v1",
        "seed": seed,
        "repetitions": repetitions,
        "defined_repetitions": len(estimates),
        "undefined_repetitions": repetitions - len(estimates),
        "pr_auc_95_percentile": interval,
        "interval_condition": "both classes present in the resampled fleet",
        "warning": "Descriptive conditional clustered interval; few assets and one fleet limit inference.",
    }
