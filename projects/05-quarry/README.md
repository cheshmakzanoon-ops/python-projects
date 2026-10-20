# Quarry — versioned local analytics

A local incremental lakehouse for changing device measurements. It owns exact historical event identities, partition-local planning, immutable Parquet publication, snapshot isolation and recovery. PyArrow supplies bounded serialization, DuckDB supplies relational transformations, and SQLite supplies the transactional catalog.

Use Quarry when corrections, retries and deletes must produce reproducible analytical results on a single machine. Source progress and business revisions remain separate: processing a newer file never makes an older, conflicting event safe to accept.

## Run the example

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_quarry.cli demo --output /tmp/quarry-demo --seed 1729
uv run --locked python -m pp_quarry.cli benchmark --profile ci --output /tmp/quarry-ci --seed 1729
uv run --locked pytest
```

The demo writes `report.json` containing an explainable one-bucket correction plan, a rejected quality batch, an orphan recovery report, source lineage, historical query samples and an independent complete-rebuild comparison. Its `correctness_checks` must all be `true`. Output directories must be empty; cleanup requires the explicit ownership marker:

```sh
uv run --locked python -m pp_quarry.cli clean-demo --output /tmp/quarry-demo
```

## Event and query contract

An event is one UTF-8 NDJSON object or a CSV row with a JSON-encoded `payload` column:

```json
{"source_namespace":"devices","key":"sensor-1","version":1,"operation":"upsert","payload":{"device":"sensor-1","day":"2026-01-01","value":21.5}}
```

Versions are nonnegative signed 64-bit integers. Delete events require an empty payload. Highest version wins independently of arrival order. Identical historical key/version/content is a replay; different content is a conflict even after newer updates, tombstones, GC and restart.

Commands below use the checked-in example files and a fresh dataset path:

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

Published manifests must include every configured bucket and the complete normalized/facts/daily graph, including empty buckets. Readers and recovery reject missing entries before interpreting them as an empty dataset or orphaned files. Pinned queries read only the files in their committed manifest and verify each file's SHA-256, size, schema and row count before execution. An externally modified Parquet file stops a query or reused publication rather than silently changing history. Full-file verification adds I/O even when a query requests a small row limit. Checksums establish consistency with the local catalog; the filesystem and catalog remain trusted.

`Contract(fields={...})` supports arbitrary initial JSON payload schemas for integration imports. Facts always preserve canonical `payload` JSON; additional declared fields become typed nullable `payload__FIELD` columns. The domain projections `device`, `day` and `value` drive daily statistics; custom datasets without those fields have null day/device and a zero value projection. New nullable columns are supported; removals, type changes and bucket-count changes require explicit migration. See [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), [acceptance](docs/ACCEPTANCE.md) and [measured benchmarks](docs/BENCHMARKS.md).

## Design and operations

| Topic | Reference |
| --- | --- |
| Publication, fingerprints and pinned readers | [Architecture](docs/ARCHITECTURE.md) |
| Storage and retention tradeoffs | [Decisions](docs/DECISIONS.md) |
| Validation, migration, backup and recovery | [Operations](docs/OPERATIONS.md) |
| Version-preserving import from other tools | [Integration contract](docs/INTEGRATION.md) |
| Reproducible checks and historical records | [Verification](docs/VERIFICATION.md) and [acceptance mapping](docs/ACCEPTANCE.md) |
| Workload definitions and measured limitations | [Benchmarks](docs/BENCHMARKS.md) |

The supported durability scope is a local filesystem with working fsync and SQLite WAL, one writer and concurrent pinned readers. Linux is the required fault-test and benchmark platform. Historical identities grow with accepted input and stale reader pins require explicit offline administration. Cloud-object storage, distributed writers and full Delta/Iceberg compatibility are outside the product.
