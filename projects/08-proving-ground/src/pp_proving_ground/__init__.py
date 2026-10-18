"""Audited local machine-learning lifecycle with immutable identity and serving snapshots."""

from pp_proving_ground.artifacts.store import ArtifactManifest, ArtifactStore
from pp_proving_ground.data_contracts.schema import DatasetVersion, FeatureSpec, generate
from pp_proving_ground.evaluation.metrics import EvaluationReport, GatePolicy
from pp_proving_ground.experiments.identity import ExperimentSpec, RunRecord
from pp_proving_ground.registry.sqlite import (
    DeploymentGeneration,
    ModelVersion,
    PromotionDecision,
    Registry,
)
from pp_proving_ground.serving.service import Prediction, ServingProcess, ServingSnapshot
from pp_proving_ground.splits.manifest import SplitManifest, freeze

__all__ = [
    "ArtifactManifest",
    "ArtifactStore",
    "DatasetVersion",
    "DeploymentGeneration",
    "EvaluationReport",
    "ExperimentSpec",
    "FeatureSpec",
    "GatePolicy",
    "ModelVersion",
    "Prediction",
    "PromotionDecision",
    "Registry",
    "RunRecord",
    "ServingProcess",
    "ServingSnapshot",
    "SplitManifest",
    "freeze",
    "generate",
]
