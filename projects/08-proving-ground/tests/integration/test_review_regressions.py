"""Independent-review regressions: declared bytes must not be silently coerced."""

from __future__ import annotations

from contextlib import closing
from dataclasses import replace

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pp_proving_ground.data_contracts.schema import ContractError, generate, read_parquet
from pp_proving_ground.training.pipeline import fit


@pytest.mark.parametrize("column", ["row_id", "asset_id", "fault_within_horizon"])
def test_fractional_integer_contract_column_never_recovers_original_digest(tmp_path, column):
    data = generate(rows=1000, features=4, assets=10)
    path = tmp_path / "fractional.parquet"
    data.write_parquet(path)
    table = pq.read_table(path)
    values = np.asarray(table[column], dtype=np.float64) + 0.25
    changed = table.set_column(table.column_names.index(column), column, pa.array(values))
    # Preserve ORIGINAL metadata. Hashing a lossy integer cast formerly matched the original data.
    assert changed.schema.metadata[b"dataset_digest"].decode() == data.identity
    pq.write_table(changed, path)
    with pytest.raises(ContractError, match="schema|type"):
        read_parquet(path)


@pytest.mark.parametrize("column", ["sensor_00", "observed_at", "sensor_00__available_at"])
def test_float32_schema_change_rejected_before_coercion(tmp_path, column):
    data = generate(rows=1000, features=4, assets=10)
    path = tmp_path / "narrowed.parquet"
    data.write_parquet(path)
    table = pq.read_table(path)
    changed = table.set_column(
        table.column_names.index(column), column, table[column].cast(pa.float32())
    )
    pq.write_table(changed, path)
    with pytest.raises(ContractError, match="schema|type"):
        read_parquet(path)


def test_duplicate_parquet_columns_refused(tmp_path):
    data = generate(rows=1000, features=4, assets=10)
    path = tmp_path / "duplicate.parquet"
    data.write_parquet(path)
    table = pq.read_table(path)
    duplicated = table.append_column("row_id", table["row_id"])
    pq.write_table(duplicated, path)
    with pytest.raises(ContractError, match="schema|columns"):
        read_parquet(path)


@pytest.mark.parametrize(
    "estimator, parameters",
    [("logistic", {"max_iter": 100}), ("tree", {"max_depth": 3, "min_samples_leaf": 5})],
)
def test_user_hyperparameters_override_defaults_without_duplicate_keyword_failure(
    data, split, estimator, parameters
):
    result = fit(data, split, estimator, parameters=parameters)
    configured = result.pipeline.named_steps["classifier"].get_params()
    assert all(configured[key] == value for key, value in parameters.items())
    assert result.train_rows == len(split.train)


def test_unknown_hyperparameter_has_clear_validation_failure(data, split):
    with pytest.raises(ValueError, match="Invalid parameter"):
        fit(data, split, "tree", parameters={"unknown": 3})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_split_policy_values_fail_closed(data, split, value):
    for field in ["embargo_hours", "validation_boundary", "test_boundary"]:
        with pytest.raises(ContractError):
            replace(split, **{field: value}).validate(data)


def test_fractional_and_boolean_manifest_indices_refused(data, split):
    for index in [0.5, True]:
        broken = replace(split, train=(index,) + split.train[1:])
        with pytest.raises(ContractError, match="integer indices"):
            broken.validate(data)


def test_registry_refuses_unrelated_and_future_version_files(tmp_path):
    import sqlite3

    from pp_proving_ground.artifacts.store import ArtifactStore
    from pp_proving_ground.registry.sqlite import Registry

    store = ArtifactStore(tmp_path / "artifacts")
    unrelated = tmp_path / "unrelated.db"
    with closing(sqlite3.connect(unrelated)) as conn, conn:
        conn.execute("CREATE TABLE precious(value TEXT)")
        conn.execute("INSERT INTO precious VALUES('keep')")
    with pytest.raises(ValueError, match="unsupported registry"):
        Registry(unrelated, store)
    with closing(sqlite3.connect(unrelated)) as conn, conn:
        assert conn.execute("SELECT value FROM precious").fetchone()[0] == "keep"
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    path = tmp_path / "registry.db"
    Registry(path, store)
    with closing(sqlite3.connect(path)) as conn, conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("PRAGMA application_id").fetchone()[0] == 1347430193
        conn.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="unsupported registry"):
        Registry(path, store)


def test_integer_null_is_not_a_valid_unchanged_dataset(tmp_path):
    data = generate(rows=1000, features=4, assets=10)
    path = tmp_path / "null-identity.parquet"
    data.write_parquet(path)
    table = pq.read_table(path)
    values = table["asset_id"].to_pylist()
    values[0] = None
    table = table.set_column(
        table.column_names.index("asset_id"), "asset_id", pa.array(values, type=pa.int64())
    )
    pq.write_table(table, path)
    with pytest.raises(ContractError, match="null required"):
        read_parquet(path)
