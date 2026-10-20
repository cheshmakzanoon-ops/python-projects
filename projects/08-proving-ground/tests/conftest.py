from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pp_proving_ground.artifacts.store import ArtifactManifest, ArtifactStore
from pp_proving_ground.data_contracts.schema import DatasetVersion, generate
from pp_proving_ground.evaluation.metrics import EvaluationReport, evaluate
from pp_proving_ground.registry.sqlite import ModelVersion, Registry
from pp_proving_ground.splits.manifest import SplitManifest, freeze
from pp_proving_ground.training.pipeline import TrainingResult, fit


@pytest.fixture(scope="session")
def data() -> DatasetVersion:
    return generate()


@pytest.fixture(scope="session")
def split(data: DatasetVersion) -> SplitManifest:
    return freeze(data)


@pytest.fixture(scope="session")
def trained(data: DatasetVersion, split: SplitManifest) -> TrainingResult:
    return fit(data, split, "logistic")


@dataclass
class Context:
    store: ArtifactStore
    registry: Registry
    manifest: ArtifactManifest
    report: EvaluationReport
    model: ModelVersion
    trained: TrainingResult


@pytest.fixture
def context(
    tmp_path: Path, data: DatasetVersion, split: SplitManifest, trained: TrainingResult
) -> Context:
    store = ArtifactStore(tmp_path / "artifacts")
    manifest = store.publish(
        trained, "a" * 64, data.identity, split.identity, tuple(f.name for f in data.schema)
    )
    report = evaluate(store, data, split, manifest.identity, bootstrap_repetitions=20)
    registry = Registry(tmp_path / "registry.db", store)
    model = registry.register(manifest.identity, report)
    return Context(store, registry, manifest, report, model, trained)
