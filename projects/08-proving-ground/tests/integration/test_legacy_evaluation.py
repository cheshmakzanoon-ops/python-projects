"""Actual baseline evidence stays readable but cannot authorize a new deployment."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from pp_proving_ground.artifacts.store import ArtifactStore
from pp_proving_ground.cli import main, prepare_output, stage_reevaluate_registry
from pp_proving_ground.data_contracts.schema import generate
from pp_proving_ground.evaluation.metrics import GatePolicy
from pp_proving_ground.experiments.identity import atomic_json, canonical, file_hash
from pp_proving_ground.registry.sqlite import Registry
from pp_proving_ground.splits.manifest import freeze


@pytest.fixture
def legacy(tmp_path):
    raw = json.loads((Path(__file__).parents[1] / "fixtures/legacy-evaluation-v1.json").read_text())
    output = prepare_output(tmp_path / "legacy")
    data = generate(**raw["dataset"])
    split = freeze(data)
    assert data.identity == raw["dataset_digest"]
    assert split.identity == raw["split_digest"]
    data.write_parquet(output / "dataset.parquet")
    from dataclasses import asdict

    atomic_json(output / "split.json", {**asdict(split), "identity": split.identity})
    store = ArtifactStore(output / "models")
    directory = store.path(raw["artifact_digest"])
    directory.mkdir()
    archive = base64.b64decode(raw["model_skops_base64"], validate=True)
    assert hashlib.sha256(archive).hexdigest() == raw["archive_sha256"]
    assert hashlib.sha256(raw["registry_sql"].encode()).hexdigest() == raw["registry_sql_sha256"]
    (directory / "model.skops").write_bytes(archive)
    (directory / "manifest.json").write_bytes(canonical(raw["manifest"]))
    with closing(sqlite3.connect(output / "registry.sqlite3")) as conn:
        conn.executescript(raw["registry_sql"])
        conn.execute(f"PRAGMA application_id={raw['application_id']}")
        conn.execute(f"PRAGMA user_version={raw['user_version']}")
        conn.commit()
    return output, store, raw


def test_legacy_default_and_explicit_policy_cannot_restore_promotion_authority(legacy):
    output, store, raw = legacy
    path = output / "registry.sqlite3"
    before = file_hash(path)
    with pytest.raises(ValueError, match="frozen policy"):
        Registry(path, store)
    with pytest.raises(ValueError, match="legacy promotion policy is read-only"):
        Registry(path, store, GatePolicy(version="validation-v1"))
    assert file_hash(path) == before
    reader = Registry.open_read_only(path, store)
    report = reader.report(1)
    assert report.version == 1
    assert report.identity == raw["report_digest"]
    assert report.metrics["pr_auc"] > 0.84  # The historical statistics belonged to logistic.
    assert reader.current().generation == 1
    assert reader.audit()[0]["accepted"] is True
    assert GatePolicy().judge(report)
    for action in [
        lambda: reader.promote(1, 1),
        lambda: reader.register(raw["artifact_digest"], report),
    ]:
        with pytest.raises(ValueError, match="read-only"):
            action()
    with reader.connection() as conn, pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM audit")
    assert file_hash(path) == before


@pytest.mark.parametrize("corrupt", [False, True])
def test_reassessment_preserves_history_and_leaves_deployment_unset(legacy, tmp_path, corrupt):
    output, store, raw = legacy
    before = file_hash(output / "registry.sqlite3")
    if corrupt:
        (store.path(raw["artifact_digest"]) / "model.skops").write_bytes(b"corrupt")
    destination = tmp_path / "reassessed/registry.sqlite3"
    result = stage_reevaluate_registry(output, destination)
    reader = Registry.open_read_only(output / "registry.sqlite3", store)
    target = Registry(destination, store)
    assert file_hash(output / "registry.sqlite3") == before
    assert reader.report(1).identity == raw["report_digest"]
    assert reader.current().generation == 1
    assert result["source_deployment"]["generation"] == 1
    assert target.current().generation == 0
    assert target.audit() == ()
    saved = json.loads(destination.with_name(destination.name + ".reevaluation.json").read_text())
    assert saved["target_deployment"]["model_version"] is None
    if corrupt:
        assert result["status"] == "partial"
        assert len(result["errors"]) == 1
        assert result["reevaluations"] == []
        assert target.versions() == ()
    else:
        assert result["status"] == "completed"
        assert result["errors"] == []
        assert result["reevaluations"][0]["source_evaluation"] == raw["report_digest"]
        new_report = target.report(1)
        assert new_report.version == 2
        assert new_report.metrics["roc_auc"] == 0.5
        assert new_report.metrics["pr_auc"] == new_report.metrics["class_balance"]
        assert new_report.identity != reader.report(1).identity
        assert len(result["reevaluations"][0]["promotion_failures"]) == 3
    with pytest.raises(ValueError, match="report already exists"):
        stage_reevaluate_registry(output, destination)


def test_existing_report_path_prevents_destination_creation(legacy, tmp_path):
    output, _, _ = legacy
    destination = tmp_path / "new.db"
    destination.with_name(destination.name + ".reevaluation.json").write_text("preserve")
    with pytest.raises(ValueError, match="report already exists"):
        stage_reevaluate_registry(output, destination)
    assert not destination.exists()


def test_legacy_cli_inspection_and_partial_migration_status(legacy, tmp_path, capsys):
    output, store, raw = legacy
    assert main(["inspect", "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["deployment"]["generation"] == 1
    (store.path(raw["artifact_digest"]) / "model.skops").unlink()
    assert (
        main(
            [
                "reevaluate-registry",
                "--output",
                str(output),
                "--destination",
                str(tmp_path / "new.db"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "partial"


def test_old_report_cannot_be_registered_in_a_new_registry(context, tmp_path):
    target = Registry(tmp_path / "v2.db", context.store)
    with pytest.raises(ValueError, match="schema-v2"):
        target.register(context.manifest.identity, replace(context.report, version=1))
    assert target.versions() == ()


def test_operator_can_train_and_deploy_reevaluated_target_without_replacing_history(
    legacy, tmp_path, capsys
):
    from pp_proving_ground.cli import stage_train
    from pp_proving_ground.serving.service import ServingProcess

    output, store, raw = legacy
    destination = tmp_path / "adopted.db"
    stage_reevaluate_registry(output, destination)
    # The reevaluated prior fails; a new logistic candidate can use the fresh registry.
    trained = stage_train(output, "logistic", 1729, destination)
    assert trained["promotion_failures"] == ()
    assert trained["model_version"] == 2
    assert (
        main(
            [
                "promote",
                "--output",
                str(output),
                "--registry",
                str(destination),
                "--version",
                "2",
                "--expected-generation",
                "0",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["generation"] == 1
    assert main(["inspect", "--output", str(output), "--registry", str(destination)]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["registry_path"] == str(destination)
    assert inspected["deployment"]["model_version"] == 2
    target = Registry(destination, store)
    process = ServingProcess(target)
    assert process.refresh()
    assert process.predict(generate().features[:2]).model_version == 2
    process.close()
    historical = Registry.open_read_only(output / "registry.sqlite3", store)
    assert historical.current().model_version == 1
    assert historical.report(1).identity == raw["report_digest"]
    assert len(historical.audit()) == 1


def test_explicit_legacy_audit_handle_cannot_start_serving(legacy):
    from pp_proving_ground.serving.service import ServingProcess

    output, store, _ = legacy
    historical = Registry.open_read_only(output / "registry.sqlite3", store)
    with pytest.raises(ValueError, match="audit-only"):
        ServingProcess(historical)
