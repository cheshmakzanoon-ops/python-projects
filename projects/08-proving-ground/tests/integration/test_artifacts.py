from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, replace

import numpy as np
import pytest
import skops.io as sio

from pp_proving_ground.artifacts.store import ArtifactError
from pp_proving_ground.experiments.identity import canonical, file_hash
from pp_proving_ground.training.pipeline import predict


class UnreviewedModel:
    value = 1


def rewrite_manifest(context, **updates):
    new = replace(context.manifest, **updates)
    destination = context.store.path(new.identity)
    shutil.copytree(context.store.path(context.manifest.identity), destination)
    (destination / "manifest.json").write_bytes(canonical(asdict(new)))
    return new


def test_loaded_pipeline_reproduces_predictions(context, data):
    pipeline, manifest = context.store.load(context.manifest.identity)
    np.testing.assert_allclose(
        predict(pipeline, data.features[:100]),
        predict(context.trained.pipeline, data.features[:100]),
        rtol=0,
        atol=1e-12,
    )
    assert manifest == context.manifest
    # Repeated serialization need not have identical bytes (skops has object IDs).
    # Semantic retries may publish another immutable artifact, preserving the original.
    original_hash = file_hash(context.store.path(context.manifest.identity) / "model.skops")
    repeated = context.store.publish(
        context.trained,
        "a" * 64,
        data.identity,
        context.manifest.split_digest,
        context.manifest.feature_names,
    )
    again, _ = context.store.load(repeated.identity)
    np.testing.assert_allclose(
        predict(again, data.features[:100]), predict(pipeline, data.features[:100]), atol=1e-12
    )
    assert file_hash(context.store.path(context.manifest.identity) / "model.skops") == original_hash


@pytest.mark.parametrize(
    "kind",
    [
        "model",
        "manifest",
        "format",
        "libraries",
        "estimator",
        "serialization",
        "symlink",
        "missing",
    ],
)
def test_corrupted_unsupported_artifacts_refused(context, kind, tmp_path):
    identity = context.manifest.identity
    directory = context.store.path(identity)
    if kind == "model":
        with (directory / "model.skops").open("ab") as stream:
            stream.write(b"tamper")
    elif kind == "manifest":
        document = json.loads((directory / "manifest.json").read_text())
        document["run_identity"] = "tamper"
        (directory / "manifest.json").write_text(json.dumps(document))
    elif kind == "format":
        identity = rewrite_manifest(context, format_version=999).identity
    elif kind == "libraries":
        identity = rewrite_manifest(context, environment={"scikit-learn": "0.0"}).identity
    elif kind == "estimator":
        identity = rewrite_manifest(context, estimator="arbitrary").identity
    elif kind == "serialization":
        identity = rewrite_manifest(context, serialization="pickle").identity
    elif kind == "symlink":
        target = tmp_path / "model"
        (directory / "model.skops").rename(target)
        (directory / "model.skops").symlink_to(target)
    else:
        (directory / "model.skops").unlink()
    with pytest.raises(ArtifactError):
        context.store.load(identity)


def test_unreviewed_custom_model_rejected_even_with_valid_checksum(context, tmp_path):
    model = tmp_path / "unreviewed.skops"
    sio.dump(UnreviewedModel(), model)
    manifest = replace(context.manifest, model_sha256=file_hash(model))
    directory = context.store.path(manifest.identity)
    directory.mkdir()
    shutil.copyfile(model, directory / "model.skops")
    (directory / "manifest.json").write_bytes(canonical(asdict(manifest)))
    with pytest.raises(ArtifactError, match="unreviewed"):
        context.store.load(manifest.identity)
    for invalid in ["../../secret", "a" * 63, "G" * 64]:
        with pytest.raises(ArtifactError):
            context.store.load(invalid)


def test_interrupted_publish_and_actual_process_exit_recover(context, data, tmp_path):
    before = set(context.store.root.iterdir())
    with pytest.raises(InterruptedError):
        context.store.publish(
            context.trained,
            "c" * 64,
            data.identity,
            context.manifest.split_digest,
            context.manifest.feature_names,
            interrupt_before_publish=True,
        )
    assert set(context.store.root.iterdir()) == before
    # Crash a child after a staged serialization write, before manifest/rename.
    code = """
import os, sys
from pathlib import Path
from pp_proving_ground.artifacts.store import ArtifactStore
from pp_proving_ground.data_contracts.schema import generate
from pp_proving_ground.splits.manifest import freeze
from pp_proving_ground.training.pipeline import fit
import pp_proving_ground.artifacts.store as module
real = module.sio.dump
def crash(model, path):
    real(model, path)
    os._exit(73)
module.sio.dump = crash
data = generate(rows=1000, assets=10)
split = freeze(data)
store = ArtifactStore(Path(sys.argv[1]))
store.publish(fit(data, split, 'logistic'), 'crashed-run', data.identity, split.identity, tuple(f.name for f in data.schema))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(context.store.root)],
        timeout=30,
        capture_output=True,
        env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
    )
    assert result.returncode == 73, result.stderr.decode()
    assert any(p.name.startswith(".stage-") for p in context.store.root.iterdir())
    assert context.store.recover_staging() == 1
    assert set(context.store.root.iterdir()) == before
    context.store.load(context.manifest.identity)


def test_malformed_but_checksummed_skops_and_supported_type_wrong_structure(context, tmp_path):
    from sklearn.dummy import DummyClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import MinMaxScaler

    payloads = [b"not-a-zip"]
    for model in [
        DummyClassifier(),
        Pipeline([("wrong", DummyClassifier())]),
        Pipeline(
            [
                ("imputer", MinMaxScaler()),
                ("scaler", MinMaxScaler()),
                ("classifier", DummyClassifier()),
            ]
        ),
    ]:
        path = tmp_path / "model.skops"
        sio.dump(model, path)
        payloads.append(path.read_bytes())
    for content in payloads:
        path = tmp_path / "model.skops"
        path.write_bytes(content)
        manifest = replace(context.manifest, model_sha256=file_hash(path))
        destination = context.store.path(manifest.identity)
        destination.mkdir()
        (destination / "manifest.json").write_bytes(canonical(asdict(manifest)))
        (destination / "model.skops").write_bytes(content)
        with pytest.raises(ArtifactError):
            context.store.load(manifest.identity)


def test_artifact_write_refuses_custom_types_and_recovery_preserves_nonstage(context, data):
    from sklearn.pipeline import Pipeline

    from pp_proving_ground.training.pipeline import TrainingResult

    bad = TrainingResult(
        Pipeline([("classifier", UnreviewedModel())]),
        "logistic",
        0,
        "none",
        data.identity,
        context.manifest.split_digest,
        context.manifest.feature_names,
    )
    with pytest.raises(ArtifactError, match="unreviewed"):
        context.store.publish(
            bad,
            "d" * 64,
            data.identity,
            context.manifest.split_digest,
            context.manifest.feature_names,
        )
    unrelated = context.store.root / "user-file"
    unrelated.write_text("preserve")
    assert context.store.recover_staging() == 0
    assert unrelated.read_text() == "preserve"
