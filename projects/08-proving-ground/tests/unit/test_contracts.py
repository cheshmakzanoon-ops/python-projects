from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from pp_proving_ground.data_contracts.schema import ContractError, FeatureSpec, generate
from pp_proving_ground.experiments.identity import ExperimentSpec, RunRecord
from pp_proving_ground.splits.manifest import freeze
from pp_proving_ground.training.pipeline import fit


def test_temporal_purge_embargo_and_entity_question(data, split):
    assert max(data.label_available_at[list(split.train)]) < split.validation_boundary
    assert min(data.observed_at[list(split.validation)]) >= split.validation_boundary + 2
    assert max(data.label_available_at[list(split.validation)]) < split.test_boundary
    assert min(data.observed_at[list(split.test)]) >= split.test_boundary + 2
    assert set(data.assets[list(split.train)]) & set(data.assets[list(split.validation)])
    entity = freeze(data, "entity")
    assert not set(data.assets[list(entity.train)]) & set(data.assets[list(entity.validation)])
    assert "not a future forecasting" in entity.question
    assert set(entity.train + entity.validation + entity.test) == set(range(len(data.labels)))


@pytest.mark.parametrize(
    "violation",
    [
        "overlap",
        "bounds",
        "empty",
        "dataset",
        "version",
        "purge",
        "embargo",
        "policy",
        "test_embargo",
        "validation_purge",
    ],
)
def test_manifest_rejects_broken_memberships(data, split, violation):
    if violation == "overlap":
        broken = replace(split, validation=split.validation + (split.train[0],))
    elif violation == "bounds":
        broken = replace(split, train=(-1,) + split.train[1:])
    elif violation == "empty":
        broken = replace(split, test=())
    elif violation == "dataset":
        broken = replace(split, dataset_digest="wrong")
    elif violation == "version":
        broken = replace(split, version=2)
    elif violation == "purge":
        broken = replace(split, validation_boundary=1)
    elif violation == "embargo":
        broken = replace(split, embargo_hours=100)
    elif violation == "policy":
        broken = replace(split, policy="other")
    elif violation == "test_embargo":
        broken = replace(split, test=(split.validation[-1],), validation=split.validation[:-1])
    else:
        broken = replace(
            split, test_boundary=float(data.label_available_at[list(split.validation)].min())
        )
    with pytest.raises(ContractError):
        broken.validate(data)


def test_entity_overlap_rejected(data):
    entity = freeze(data, "entity")
    existing = data.assets[entity.train[0]]
    moved = next(i for i in entity.train[1:] if data.assets[i] == existing)
    broken = replace(
        entity,
        train=tuple(i for i in entity.train if i != moved),
        validation=entity.validation + (moved,),
    )
    with pytest.raises(ContractError, match="entity holdout overlap"):
        broken.validate(data)


@pytest.mark.parametrize("kind", ["future", "derived"])
def test_unavailable_and_declared_future_derived_features(data, kind):
    if kind == "future":
        available = data.feature_available_at.copy()
        available[100, 1] += 1
        broken = replace(data, feature_available_at=available)
    else:
        schema = (FeatureSpec("post_fault_alarm", label_derived=True),) + data.schema[1:]
        broken = replace(data, schema=schema)
    with pytest.raises(ContractError):
        freeze(broken)


def test_train_only_preprocessing_independent_median(data, split):
    values = data.features.copy()
    values[list(split.validation), 0] = 1e9
    values[list(split.test), 0] = -1e12
    modified = replace(data, features=values)
    changed_split = replace(split, dataset_digest=modified.identity)
    result = fit(modified, changed_split, "logistic")
    actual = result.pipeline.named_steps["imputer"].statistics_
    np.testing.assert_allclose(
        actual, np.nanmedian(values[list(split.train)], axis=0), rtol=0, atol=0
    )
    assert actual[0] != np.nanmedian(values[:, 0])


def test_dataset_reproducibility_and_parquet_provenance(tmp_path):
    a, b = generate(seed=19), generate(seed=19)
    assert a.identity == b.identity
    assert a.identity != generate(seed=20).identity
    assert freeze(a).identity == freeze(b).identity
    path = tmp_path / "dataset.parquet"
    a.write_parquet(path)
    table = pq.read_table(path)
    assert table.num_rows == 5000
    assert table.schema.metadata[b"dataset_digest"].decode() == a.identity
    assert "sensor_00__available_at" in table.column_names
    with pytest.raises(ValueError):
        a.features[0, 0] = 1


def test_semantic_identity_and_attempts(tmp_path: Path):
    spec = ExperimentSpec("a", "b", "c", "median", "logistic", {"C": 1}, 1729, "lock")
    assert spec.identity == replace(spec, parameters={"C": 1}).identity
    for field, value in [
        ("dataset_digest", "x"),
        ("split_digest", "x"),
        ("code_digest", "x"),
        ("preprocessing", "x"),
        ("parameters", {"C": 2}),
        ("seed", 10),
        ("lock_digest", "x"),
    ]:
        assert replace(spec, **{field: value}).identity != spec.identity
    a, b = RunRecord.begin(spec, tmp_path, {}), RunRecord.begin(spec, tmp_path, {})
    assert a.experiment_id == b.experiment_id
    assert a.attempt_id != b.attempt_id
    assert len(list((tmp_path / spec.identity).glob("*.json"))) == 3
    assert (tmp_path / spec.identity / "spec.json").exists()


@pytest.mark.parametrize(
    "kind",
    [
        "features_count",
        "schema_type",
        "dtype",
        "duplicate_names",
        "vector_shape",
        "duplicate_ids",
        "nonbinary",
        "horizon",
        "infinite_time",
        "infinite_availability",
        "infinite_feature",
        "early_label",
        "declared_offset",
    ],
)
def test_dataset_contract_failure_boundaries(data, kind):
    kwargs = {}
    if kind == "features_count":
        kwargs["schema"] = data.schema[:3]
    elif kind == "schema_type":
        kwargs["schema"] = (replace(data.schema[0], kind="object"),) + data.schema[1:]
    elif kind == "dtype":
        kwargs["row_ids"] = data.row_ids.astype(float)
    elif kind == "duplicate_names":
        kwargs["schema"] = (data.schema[1],) + data.schema[1:]
    elif kind == "vector_shape":
        kwargs["assets"] = data.assets[:3]
    elif kind == "duplicate_ids":
        ids = data.row_ids.copy()
        ids[0] = ids[1]
        kwargs["row_ids"] = ids
    elif kind == "nonbinary":
        labels = data.labels.copy()
        labels[0] = 7
        kwargs["labels"] = labels
    elif kind == "horizon":
        kwargs["horizon_hours"] = float("nan")
    elif kind == "infinite_time":
        times = data.observed_at.copy()
        times[0] = float("inf")
        kwargs["observed_at"] = times
    elif kind == "infinite_availability":
        available = data.feature_available_at.copy()
        available[0, 0] = np.nan
        kwargs["feature_available_at"] = available
    elif kind == "infinite_feature":
        features = data.features.copy()
        features[0, 0] = np.inf
        kwargs["features"] = features
    elif kind == "early_label":
        labels = data.label_available_at.copy()
        labels[0] = 0
        kwargs["label_available_at"] = labels
    else:
        kwargs["schema"] = (replace(data.schema[0], availability_offset_hours=1),) + data.schema[1:]
    with pytest.raises(ContractError):
        replace(data, **kwargs).validate_availability()


def test_split_api_rejects_invalid_roles_policy_and_negative_embargo(data, split):
    with pytest.raises(ContractError):
        split.indices("development")
    with pytest.raises(ContractError):
        freeze(data, "random")
    with pytest.raises(ContractError):
        freeze(data, embargo_hours=-1)
    with pytest.raises(ContractError):
        freeze(data, embargo_hours=10000)
    with pytest.raises(ContractError):
        generate(rows=20)


def test_semantic_retry_refuses_tampered_specification(tmp_path):
    spec = ExperimentSpec("a", "b", "c", "median", "logistic", {}, 1729, "lock")
    RunRecord.begin(spec, tmp_path, {})
    (tmp_path / spec.identity / "spec.json").write_text("{}")
    with pytest.raises(ValueError, match="specification differs"):
        RunRecord.begin(spec, tmp_path, {})
