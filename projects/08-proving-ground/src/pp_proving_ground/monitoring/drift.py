"""Descriptive distribution comparisons are not an accuracy-degradation test."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pp_proving_ground.data_contracts.schema import FloatArray


def drift_report(
    reference: FloatArray,
    incoming: FloatArray,
    expected_names: tuple[str, ...],
    incoming_names: tuple[str, ...],
) -> dict[str, Any]:
    if reference.ndim != 2 or incoming.ndim != 2 or reference.shape[1] != len(expected_names):
        raise ValueError("invalid reference dimensions")
    errors: list[str] = []
    if incoming_names != expected_names or incoming.shape[1] != reference.shape[1]:
        errors.append("feature names/order or count changed")
    if np.isinf(incoming).any():
        errors.append("infinite feature values")
    if not len(reference) or not len(incoming):
        errors.append("empty reference or incoming batch")
    result: dict[str, Any] = {
        "schema_version": 1,
        "schema_failures": errors,
        "reference_count": len(reference),
        "incoming_count": len(incoming),
        "interpretation": "Distribution shift only; accuracy requires outcome labels.",
        "features": [],
    }
    if errors:
        return result
    for i, name in enumerate(expected_names):
        a, b = reference[:, i], incoming[:, i]
        finite_a, finite_b = a[np.isfinite(a)], b[np.isfinite(b)]
        std = float(np.std(finite_a)) if len(finite_a) else 0.0
        shift = (
            float(finite_b.mean() - finite_a.mean()) / max(std, 1e-9)
            if len(finite_a) and len(finite_b)
            else None
        )
        edges = (
            np.unique(np.quantile(finite_a, np.linspace(0, 1, 11)))
            if len(finite_a)
            else np.array([])
        )
        psi: float | None = None
        if len(edges) > 1 and len(finite_b):
            edges[0], edges[-1] = -math.inf, math.inf
            left = np.histogram(finite_a, edges)[0] / len(finite_a)
            right = np.histogram(finite_b, edges)[0] / len(finite_b)
            left, right = np.maximum(left, 1e-6), np.maximum(right, 1e-6)
            psi = float(np.sum((right - left) * np.log(right / left)))
        result["features"].append(
            {
                "feature": name,
                "standardized_mean_shift": shift,
                "reference_missing_rate": float(np.isnan(a).mean()),
                "incoming_missing_rate": float(np.isnan(b).mean()),
                "psi": psi,
            }
        )
    return result
