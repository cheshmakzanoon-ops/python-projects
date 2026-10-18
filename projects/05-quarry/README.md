# Quarry

A local incremental lakehouse for changing device measurements. It owns exact historical event identities, partition-local planning, immutable Parquet publication, snapshot isolation and recovery. PyArrow supplies bounded serialization, DuckDB supplies relational transformations, and SQLite supplies the transactional catalog.

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_quarry.cli demo --output /tmp/quarry-demo --seed 1729
uv run --locked python -m pp_quarry.cli benchmark --profile ci --output /tmp/quarry-ci --seed 1729
uv run --locked pytest
```

The demo writes `report.json`, an explainable one-bucket correction plan, a rejected quality batch, an orphan recovery report, source lineage, historical query samples and an independent complete-rebuild comparison. Output directories must be empty; cleanup requires the explicit ownership marker:

```sh
uv run --locked python -m pp_quarry.cli clean-demo --output /tmp/quarry-demo
```

An event is one UTF-8 NDJSON object or a CSV row with a JSON-encoded `payload` column:

```json
{"source_namespace":"devices","key":"sensor-1","version":1,"operation":"upsert","payload":{"device":"sensor-1","day":"2026-01-01","value":21.5}}
```

Versions are nonnegative signed 64-bit integers. Delete events require an empty payload. Highest version wins independently of arrival order. Identical historical key/version/content is a replay; different content is a conflict even after newer updates, tombstones, GC and restart.

```sh
uv run --locked quarry ingest --dataset /tmp/my-lake --source examples/devices.ndjson
uv run --locked quarry plan --dataset /tmp/my-lake --source examples/correction.ndjson
uv run --locked quarry query --dataset /tmp/my-lake --node daily
uv run --locked quarry snapshots --dataset /tmp/my-lake
uv run --locked quarry lineage --dataset /tmp/my-lake --namespace devices --key sensor-1
uv run --locked quarry validate --dataset /tmp/my-lake
uv run --locked quarry recover --dataset /tmp/my-lake
uv run --locked quarry gc --dataset /tmp/my-lake --retain 3
```

The API is independent of the CLI:

```python
from pp_quarry import Lakehouse, Snapshot

with Lakehouse("/tmp/my-lake") as lake:
    snapshot = lake.ingest("examples/devices.ndjson")
    with Snapshot(lake.root, snapshot) as pinned:
        for fact in pinned.rows():
            print(fact["key"], fact["payload"])
```

`Contract(fields={...})` supports arbitrary initial JSON payload schemas for integration imports. Facts always preserve canonical `payload` JSON; additional declared fields become typed nullable `payload__FIELD` columns. The domain projections `device`, `day` and `value` drive daily statistics; custom datasets without those fields have null day/device and a zero value projection. New nullable columns are supported; removals, type changes and bucket-count changes require explicit migration. See [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), [acceptance](docs/ACCEPTANCE.md) and [measured benchmarks](docs/BENCHMARKS.md).

The supported durability scope is a local filesystem with working fsync and SQLite WAL, one writer and concurrent pinned readers. Linux is the required fault-test and benchmark platform. Cloud-object storage, distributed writers and full Delta/Iceberg compatibility are outside the product.
