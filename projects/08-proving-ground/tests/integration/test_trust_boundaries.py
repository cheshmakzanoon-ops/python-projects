from __future__ import annotations

import copy
import errno
import json
import os
import shutil
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest
import skops.io as sio
from fastapi.testclient import TestClient

from pp_proving_ground.artifacts.store import ArtifactError
from pp_proving_ground.experiments.identity import canonical, file_hash
from pp_proving_ground.serving.api import create_app
from pp_proving_ground.serving.service import ServingProcess


def install_artifact(context, manifest, model: bytes | None = None):
    destination = context.store.path(manifest.identity)
    shutil.copytree(context.store.path(context.manifest.identity), destination)
    (destination / "manifest.json").write_bytes(canonical(asdict(manifest)))
    if model is not None:
        (destination / "model.skops").write_bytes(model)
    return manifest.identity


@pytest.mark.parametrize(
    "updates",
    [
        {"format_version": True},
        {"format_version": 1.0},
        {"feature_names": ()},
        {"feature_names": ("sensor_00", "sensor_00")},
        {"feature_names": "sensor"},
        {"feature_names": (1, "sensor_00")},
        {"run_identity": "not-a-content-digest"},
        {"dataset_digest": "a" * 63},
        {"split_digest": "Z" * 64},
    ],
)
def test_checksummed_manifest_still_requires_canonical_schema(context, updates):
    identity = install_artifact(context, replace(context.manifest, **updates))
    with pytest.raises(ArtifactError):
        context.store.inspect(identity)


@pytest.mark.parametrize("member", ["manifest.json", "model.skops"])
def test_special_artifact_members_refused_without_opening_them(context, member):
    path = context.store.path(context.manifest.identity) / member
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(ArtifactError, match="regular files"):
        context.store.inspect(context.manifest.identity)


@pytest.mark.parametrize(
    "defect", ["order", "duplicate_step", "feature_count", "imputer", "scaler"]
)
def test_supported_types_do_not_authorize_a_different_pipeline_contract(context, tmp_path, defect):
    pipeline = copy.deepcopy(context.trained.pipeline)
    names = context.manifest.feature_names
    if defect == "order":
        pipeline.steps[:2] = reversed(pipeline.steps[:2])
    elif defect == "duplicate_step":
        pipeline.steps.insert(1, pipeline.steps[0])
    elif defect == "feature_count":
        names = names[:-1]
    elif defect == "imputer":
        pipeline.named_steps["imputer"].strategy = "mean"
    else:
        pipeline.named_steps["scaler"].with_std = False
    model = tmp_path / "changed.skops"
    sio.dump(pipeline, model)
    manifest = replace(context.manifest, model_sha256=file_hash(model), feature_names=names)
    identity = install_artifact(context, manifest, model.read_bytes())
    with pytest.raises(ArtifactError, match="pipeline|preprocessing"):
        context.store.load(identity)


def test_artifact_publication_syncs_stage_entries_before_rename(context, data, monkeypatch):
    events = []
    real_sync, real_rename = os.fsync, os.rename

    def sync(fd):
        path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        if path.name in {"model.skops", "manifest.json"}:
            events.append(path.name)
        elif path.name.startswith(".stage-"):
            events.append("stage")
        elif path == context.store.root:
            events.append("store")
        real_sync(fd)

    def publish(source, destination):
        events.append("rename")
        real_rename(source, destination)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "rename", publish)
    context.store.publish(
        context.trained,
        "d" * 64,
        data.identity,
        context.manifest.split_digest,
        context.manifest.feature_names,
    )
    assert events == ["model.skops", "manifest.json", "stage", "rename", "store"]


def test_stage_sync_failure_preserves_published_artifacts_and_cleans_stage(
    context, data, monkeypatch
):
    before = set(context.store.root.iterdir())
    real_sync = os.fsync

    def sync(fd):
        path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        if path.name.startswith(".stage-"):
            raise OSError(errno.EIO, "injected stage synchronization failure")
        real_sync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", sync)
        with pytest.raises(OSError, match="stage synchronization"):
            context.store.publish(
                context.trained,
                "e" * 64,
                data.identity,
                context.manifest.split_digest,
                context.manifest.feature_names,
            )
    assert set(context.store.root.iterdir()) == before
    context.store.load(context.manifest.identity)


@pytest.mark.parametrize("value", [True, "0.5", "NaN", float("nan"), float("inf")])
def test_record_api_does_not_coerce_non_numeric_or_nonfinite_sensor_values(context, value):
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    record = dict.fromkeys(context.manifest.feature_names, 0.0)
    record[context.manifest.feature_names[0]] = value
    with pytest.raises(ValueError, match="finite numbers"):
        process.predict_records([record])


@pytest.mark.parametrize("value", [True, "0.5", float("nan"), float("inf"), -float("inf")])
def test_http_invalid_numeric_values_return_422_without_reflecting_input(context, value):
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    record = dict.fromkeys(context.manifest.feature_names, 0.0)
    record[context.manifest.feature_names[0]] = value
    with TestClient(create_app(process, auto_refresh=False)) as client:
        response = client.post(
            "/predict",
            content=json.dumps({"records": [record]}),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)


def test_integer_values_and_explicit_null_preserve_offline_parity(context):
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    record = dict.fromkeys(context.manifest.feature_names, 0)
    record[context.manifest.feature_names[0]] = None
    prediction = process.predict_records([record])
    with TestClient(create_app(process, auto_refresh=False)) as client:
        response = client.post("/predict", json={"records": [record]})
    assert response.status_code == 200
    assert response.json()["probabilities"] == pytest.approx(prediction.probabilities, abs=1e-12)
    assert np.isfinite(prediction.probabilities).all()
