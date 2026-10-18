from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pp_proving_ground.evaluation.metrics import EvaluationReport, GatePolicy
from pp_proving_ground.registry.sqlite import Registry
from pp_proving_ground.splits.manifest import SplitManifest


def model_card(
    report: EvaluationReport, split: SplitManifest, policy: GatePolicy, registry: Registry
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": "Synthetic equipment fault within six hours",
        "dataset_digest": report.dataset_digest,
        "split_digest": split.identity,
        "evaluation_question": split.question,
        "evaluation": asdict(report),
        "gate_policy": asdict(policy),
        "gate_policy_digest": policy.identity,
        "decisions": registry.audit(),
        "deployment": asdict(registry.current()),
        "limitations": [
            "Original generated data, no demonstrated real-equipment utility.",
            "Checks enforce declared availability, not undisclosed causal leakage.",
            "Asset bootstrap does not cover unseen fleet distribution uncertainty.",
            "No arbitrary model upload, pickle/joblib, or custom estimator types.",
            "Local loopback service has no authentication; do not expose publicly.",
        ],
    }
