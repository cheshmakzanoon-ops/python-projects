# Python and CLI contracts

The package exports `Config`, `Contract`, `Field`, `Lakehouse`, `Snapshot`, `Conflict`, `InjectedCrash` and `recover`. Paths refer to a local filesystem; there is no remote service or asynchronous interface. Handles own SQLite connections and belong to their creating thread. Use separate handles for concurrent readers and one application writer.

## Configure and publish

```python
from pp_quarry import Config, Contract, Field, Lakehouse

config = Config(buckets=8, batch_size=1024, memory_mb=128, threads=1)
contract = Contract(
    fields={
        "device": Field("string"),
        "day": Field("string"),
        "value": Field("number"),
        "firmware": Field("string", nullable=True),
    }
)

with Lakehouse("/tmp/device-lake", config) as lake:
    plan = lake.plan("measurements.ndjson", contract)
    snapshot_id = lake.ingest("measurements.ndjson", contract)
    manifest = lake.manifest(snapshot_id)
    assert manifest["snapshot"] == snapshot_id
```

The root must be empty or Quarry-owned. Stored bucket count cannot change on reopen. Configuration requires actual integers: batch size ≥1, DuckDB memory ≥32 MB, threads 1–2, record bound ≥128 bytes. The batch-row × record-byte envelope must fit in half the configured memory budget. Defaults are eight buckets, 1,024 rows, 128 MB, one thread and 65,536 bytes per record. These settings do not cap total process RSS.

`Contract.fields` is a copied read-only mapping of immutable `Field` values. Use `to_dict()` for a serialized mutable specification and `Contract.from_dict()` to validate one. Construct a new contract for evolution; only nullable field additions are compatible automatically. Domain fields device/day/value drive projections. Custom schemas without them project null device/day and zero value. Facts always preserve canonical payload JSON; extra fields become typed `payload__FIELD` columns with identifier/collision checks.

Events declare source_namespace, key, version, operation and payload. Versions are nonnegative signed 64-bit integers; operations are upsert/delete, and delete payloads must be empty. Greatest version wins per namespace/key independently of arrival order. Identical historical identity/content is replay; different content raises `Conflict`, including after deletion, retention and restart. The exact file-content checkpoint remains separate from business event versions.

`plan(source=None, contract=None, dag=DEFAULT_DAG)` stages in a writer transaction and always rolls back. Its base snapshot and per-bucket build/reuse decisions are diagnostic, not a reservation or proof that file/aggregate execution will pass. `ingest(source, contract=None, *, fault=None, dag=DEFAULT_DAG, force_rebuild=False)` replans and returns a committed integer snapshot ID. `build(*, force=False)` publishes current state using the stored contract; force rebuilds all nodes. The supported graph is normalized→facts→daily; node contract versions can invalidate it. Global quality runs on every publication, including checkpointed source replays.

Catalog commit makes history/checkpoint/manifest visible together after file synchronization and daily aggregate checks. Before-commit failure rolls back new catalog state but can leave orphan files. After-commit process failure is ambiguous to the caller. Reopen and retry identical content rather than inventing a compensating business version. Replay preserves identities/results but can create another metadata snapshot.

## Pinned streaming reads

```python
from pp_quarry import Snapshot

with Snapshot("/tmp/device-lake", snapshot_id) as snapshot:
    for fact in snapshot.rows("facts"):
        print(fact["key"], fact["payload"])
    daily_sample = list(snapshot.rows("daily", limit=10))
```

An omitted ID atomically selects and pins the newest committed snapshot. `rows(node="facts", limit=None)` returns a generator of dictionaries. Nodes are normalized, facts and daily; limits are nonnegative integers excluding booleans. Facts/normalized order by namespace/key; daily orders by day. The CLI defaults to 100 rows. Full export fetches batches of 1,024 and can spill for sorting.

Every selected file is checked against committed size, SHA-256, schema and count before execution. Daily results require globally finite `DOUBLE` totals before the first yielded row, even with limit 1. Arithmetic is approximate, not exact decimal; nonfinite sums raise `ValueError`. Publication and validation perform the same global range check.

Keep the context open for the full iteration. Closing a handle closes active query generators/connections before unregistering its persistent pin; suspended generators then stop. Calling rows on a closed handle fails. Abandoning an iterator frees its engine while the snapshot stays pinned. Do not resume an iterator concurrently with handle closure from another thread. Process death may leave a stale pin, requiring offline administration.

`lake.validate(snapshot_id=None)` pins and checks all files plus global daily range, returning `{"files": n, "rows": n}`. Rows sum all three physical node types, not just live facts. A fresh dataset without a snapshot returns zero. `lake.snapshots()` lists retained IDs. `lake.manifest(id=None)` returns validated metadata but does not pin files for later caller-managed access; use `Snapshot` for file reads.

## Frozen lineage pages

```python
with Lakehouse("/tmp/device-lake") as lake:
    page = lake.lineage("devices", "sensor-1", limit=1000)
    cutoff = page["as_of_snapshot"]
    while True:
        for version in page["versions"]:
            print(version["version"], version["source_sha256"])
        cursor = page["next_after_version"]
        if cursor is None:
            break
        page = lake.lineage(
            "devices",
            "sensor-1",
            after_version=cursor,
            as_of_snapshot=cutoff,
            limit=1000,
        )
```

`lineage(namespace, key, *, after_version=-1, limit=1000, as_of_snapshot=None)` returns ascending accepted versions with fingerprint, operation, source SHA-256 and offset. Limits are 1–10,000; the exclusive cursor is -1 through `2**63-1`. `next_after_version` is null at the final page; an absent key yields an empty page. This bounded default replaces the earlier unbounded response.

The first response captures the latest committed acceptance prefix. Passing that cutoff excludes identities first accepted later, even if a later source inserts an obsolete version below your cursor. Source checkpoints preserve the cutoff after materialized snapshot GC. Omitting the cutoff on later pages starts a fresh traversal. The response's columns describe the current manifest, labeled by `column_lineage_snapshot`; they are not the schema of the history cutoff.

CLI equivalents use `lineage --namespace devices --key sensor-1 --limit 1000`, then `--after-version CURSOR --as-of-snapshot CUTOFF`. Other public commands expose ingest, plan, build, validate, query, snapshots, explain, recover and gc; run `quarry COMMAND --help` for selectors.

## Recovery and exceptions

`recover(lake, *, retain=None)` takes an open `Lakehouse`, validates owned references, optionally commits snapshot retention, then reconciles orphans under a fresh writer lock. Pins override retention. Historical identities, tombstones and checkpoints remain. Recovery checks topology/ownership; validate checks content and aggregate range. See [operations](OPERATIONS.md) for backup, stale pins, retries and migration.

Invalid contract/event/resource/manifest inputs raise `ValueError`; `Conflict` specializes it for equal-version disagreement. `InjectedCrash` is a deterministic test fault. Filesystem, SQLite and DuckDB failures retain their underlying exceptions unless explicitly translated, such as aggregate range failures. Callers should retain failed source content for diagnosis, inspect committed state after interruption and retry exactly; no broad catch-and-continue policy is supplied.
