"""Original synthetic equipment contract. Times are integer hours since epoch."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pyarrow.parquet as pq

from pp_proving_ground.experiments.identity import canonical

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    availability_offset_hours: float = 0.0
    label_derived: bool = False
    kind: str = "float64"


@dataclass(frozen=True)
class DatasetVersion:
    row_ids: IntArray
    assets: IntArray
    observed_at: FloatArray
    feature_available_at: FloatArray
    label_available_at: FloatArray
    features: FloatArray
    labels: IntArray
    schema: tuple[FeatureSpec, ...]
    horizon_hours: float
    generator: str
    seed: int

    def __post_init__(self) -> None:
        n, p = self.features.shape
        if n < 10 or len(self.schema) != p:
            raise ContractError("dataset dimensions")
        if any(
            f.kind != "float64" or not np.isfinite(f.availability_offset_hours) for f in self.schema
        ):
            raise ContractError("unsupported feature contract")
        if (
            self.features.dtype != np.float64
            or self.row_ids.dtype != np.int64
            or self.labels.dtype != np.int64
            or self.assets.dtype != np.int64
            or self.observed_at.dtype != np.float64
            or self.feature_available_at.dtype != np.float64
            or self.label_available_at.dtype != np.float64
        ):
            raise ContractError("dataset types do not match schema")
        reserved = {
            "row_id",
            "asset_id",
            "observed_at",
            "label_available_at",
            "fault_within_horizon",
        }
        if any(
            not f.name or f.name in reserved or f.name.endswith("__available_at")
            for f in self.schema
        ):
            raise ContractError("reserved or empty feature name")
        if len(set(f.name for f in self.schema)) != p:
            raise ContractError("duplicate feature names")
        vectors = (
            self.row_ids,
            self.assets,
            self.observed_at,
            self.label_available_at,
            self.labels,
        )
        if any(v.shape != (n,) for v in vectors) or self.feature_available_at.shape != (n, p):
            raise ContractError("row contract dimensions")
        if len(np.unique(self.row_ids)) != n or not np.isin(self.labels, [0, 1]).all():
            raise ContractError("row IDs must be unique; labels binary")
        if (
            not np.isfinite(self.horizon_hours)
            or self.horizon_hours <= 0
            or not np.isfinite(self.observed_at).all()
        ):
            raise ContractError("invalid time contract")
        if (
            not np.isfinite(self.feature_available_at).all()
            or not np.isfinite(self.label_available_at).all()
        ):
            raise ContractError("nonfinite availability time")
        if np.isinf(self.features).any():
            raise ContractError("infinite feature value")
        if (self.label_available_at < self.observed_at + self.horizon_hours).any():
            raise ContractError("label arrives before horizon")
        for array in (*vectors, self.features, self.feature_available_at):
            array.flags.writeable = False

    @property
    def identity(self) -> str:
        h = hashlib.sha256(
            canonical(
                {
                    "format": 1,
                    "schema": [asdict(f) for f in self.schema],
                    "horizon": self.horizon_hours,
                    "generator": self.generator,
                    "seed": self.seed,
                }
            )
        )
        for array in (
            self.row_ids,
            self.assets,
            self.observed_at,
            self.feature_available_at,
            self.label_available_at,
            self.features,
            self.labels,
        ):
            contiguous = np.ascontiguousarray(array)
            h.update(str(contiguous.dtype).encode())
            h.update(canonical(contiguous.shape))
            h.update(contiguous.tobytes())
        return h.hexdigest()

    def validate_availability(self) -> None:
        if any(f.availability_offset_hours > 0 for f in self.schema):
            raise ContractError("declared feature unavailable at prediction time")
        if any(f.label_derived for f in self.schema):
            raise ContractError("declared label-derived feature")
        if (self.feature_available_at > self.observed_at[:, None]).any():
            raise ContractError("feature unavailable at prediction time")

    def write_parquet(self, path: Path) -> None:
        columns: dict[str, Any] = {
            "row_id": self.row_ids,
            "asset_id": self.assets,
            "observed_at": self.observed_at,
            "label_available_at": self.label_available_at,
            "fault_within_horizon": self.labels,
        }
        for i, feature in enumerate(self.schema):
            columns[feature.name] = self.features[:, i]
            columns[f"{feature.name}__available_at"] = self.feature_available_at[:, i]
        table = pa.table(columns)
        table = table.replace_schema_metadata(
            {
                b"dataset_digest": self.identity.encode(),
                b"contract": canonical(
                    {
                        "version": 1,
                        "horizon_hours": self.horizon_hours,
                        "generator": self.generator,
                        "seed": self.seed,
                        "features": [asdict(f) for f in self.schema],
                    }
                ),
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path, compression="zstd")


def generate(
    rows: int = 5000, features: int = 12, assets: int = 50, seed: int = 1729, drift: float = 0.0
) -> DatasetVersion:
    if rows < 100 or features < 4 or assets < 10:
        raise ContractError("need >=100 rows, >=4 features, >=10 assets")
    rng = np.random.default_rng(seed)
    ids = np.arange(rows, dtype=np.int64)
    asset_ids = ids % assets
    time = (ids // assets).astype(np.float64)
    asset_effect = rng.normal(size=assets)
    x = rng.normal(size=(rows, features))
    # Shared asset state and a slow seasonal component induce repeated-observation correlation.
    x[:, 0] += 0.5 * asset_effect[asset_ids] + 0.5 * np.sin(time / 25)
    x[:, 1] += 0.3 * np.cos(time / 17)
    x[:, 2] += time / max(float(time.max()), 1.0) * 0.3
    shift_mask = time >= np.quantile(time, 0.8)
    x[shift_mask, :3] += drift
    risk = 2.2 * x[:, 0] - 1.8 * x[:, 1] + 1.1 * x[:, 2] + 0.4 * asset_effect[asset_ids] - 2.7
    probability = 1 / (1 + np.exp(-risk))
    labels = (rng.random(rows) < probability).astype(np.int64)
    x[rng.random(x.shape) < 0.025] = np.nan
    available = np.broadcast_to(time[:, None], x.shape).copy()
    return DatasetVersion(
        ids,
        asset_ids,
        time,
        available,
        time + 6.0,
        x,
        labels,
        tuple(FeatureSpec(f"sensor_{i:02}") for i in range(features)),
        6.0,
        "equipment-fault-v1/original-synthetic",
        seed,
    )


def read_parquet(path: Path) -> DatasetVersion:
    """Read only this versioned contract; the embedded digest must match actual columns."""
    import json

    metadata = pq.read_metadata(path)
    if (
        metadata.num_rows > 1_000_000
        or metadata.num_columns > 520
        or path.stat().st_size > 2_000_000_000
    ):
        raise ContractError("dataset input limit")
    raw_metadata = metadata.metadata or {}
    try:
        contract = json.loads(raw_metadata[b"contract"])
        if contract["version"] != 1:
            raise ContractError("unsupported dataset contract")
        schema = tuple(FeatureSpec(**item) for item in contract["features"])
        arrow_schema = pq.read_schema(path)
        names = arrow_schema.names
        if len(names) != len(set(names)):
            raise ContractError("duplicate dataset columns")
        expected_types = {
            "row_id": pa.int64(),
            "asset_id": pa.int64(),
            "observed_at": pa.float64(),
            "label_available_at": pa.float64(),
            "fault_within_horizon": pa.int64(),
        }
        reserved = set(expected_types)
        for feature in schema:
            if (
                not feature.name
                or feature.name in reserved
                or feature.name.endswith("__available_at")
            ):
                raise ContractError("reserved feature name in dataset schema")
            expected_types[feature.name] = pa.float64()
            expected_types[f"{feature.name}__available_at"] = pa.float64()
        if set(names) != set(expected_types) or len(names) != len(expected_types):
            raise ContractError("unexpected dataset columns")
        if any(arrow_schema.field(name).type != dtype for name, dtype in expected_types.items()):
            raise ContractError("dataset Arrow schema type mismatch")
        table = pq.read_table(path)
        if not table.schema.equals(arrow_schema, check_metadata=True):
            raise ContractError("dataset schema changed during read")
        for name in (
            "row_id",
            "asset_id",
            "observed_at",
            "label_available_at",
            "fault_within_horizon",
        ):
            if table[name].null_count:
                raise ContractError("null required contract column")
        data = DatasetVersion(
            np.asarray(table["row_id"], dtype=np.int64),
            np.asarray(table["asset_id"], dtype=np.int64),
            np.asarray(table["observed_at"], dtype=np.float64),
            np.column_stack(
                [np.asarray(table[f"{f.name}__available_at"], dtype=np.float64) for f in schema]
            ),
            np.asarray(table["label_available_at"], dtype=np.float64),
            np.column_stack([np.asarray(table[f.name], dtype=np.float64) for f in schema]),
            np.asarray(table["fault_within_horizon"], dtype=np.int64),
            schema,
            float(contract["horizon_hours"]),
            contract["generator"],
            int(contract["seed"]),
        )
        if data.identity != raw_metadata[b"dataset_digest"].decode():
            raise ContractError("dataset content checksum mismatch")
        data.validate_availability()
        return data
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ContractError("malformed dataset contract") from error
