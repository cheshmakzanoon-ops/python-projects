# Run, diagnose and recover

## Start an owned environment

Use a dedicated PostgreSQL database and a caller-selected schema. Export its URL as
`ANCHOR_DATABASE_URL`; do not put it in definitions, history or checked-in files.
Install with `uv sync --locked --python 3.14.8` (3.13.16 is also supported).
From this project directory, start separate foreground processes:

```sh
uv run --locked anchor scheduler --schema anchor_local
uv run --locked anchor worker --schema anchor_local --concurrency 4
uv run --locked anchor serve --schema anchor_local --port 8101
```

The HTTP service is optional and binds to loopback without authentication. Keep it
local. The scheduler fires persisted timers; workers execute activities. Database rows
survive either process stopping. `drain(engine)` is a bounded helper for ready work,
not a service supervisor: future timers and missing signals remain pending.

Interrupting a worker may leave a claim alive until its database deadline. Wait for
expiry/reclaim rather than editing its epoch or task status. Choose a lease comfortably
above expected heartbeat/database latency. Lease comparisons use PostgreSQL time;
changing a worker's clock or shortening its sleep does not grant ownership.

## Inspect one run

```sh
uv run --locked anchor inspect RUN_ID --schema anchor_local
uv run --locked anchor replay RUN_ID --schema anchor_local
```

`GET /runs/RUN_ID` reconstructs the same control state. History is paginated at
`GET /runs/RUN_ID/history?after=0&limit=100`; pass `next_after` into the next request.
A history entry records its event codec, command identities, attempt, epoch, selected
retry delay and outcome. Status/replay use one consistent read snapshot; a healthy
concurrent completion does not look like a truncated log.

`/health` reports process liveness. `/ready` checks a database query, not all run
histories or available worker capacity. `Engine.metrics()` reports run/task phases,
retry/queue-delay samples and owned-schema bytes. Inspect a run's actual history before
interpreting an aggregate: `running` task state is a lease record, not proof of a live
process. A cancelled attempt is closed in accounting even if its handler is still exiting.

## Failed cleanup: repair the leaf, then resume

Suppose `allocate -> publish` has cleanup `release <- unpublish`. If `unpublish`
exhausts its retry budget, the workflow remains `compensating`, with the publication
cleanup `failed` and allocation cleanup `blocked`. This prevents releasing the parent
resource while a dependent publication still exists. Independent cleanup branches may
already have completed.

1. Inspect the failed cleanup error and the provider's current state. Keep the same
   business idempotency key; a fresh key would create a different operation.
2. Repair the provider/service or the registered handler. A handler must tolerate an
   already absent effect because an earlier attempt may have succeeded without ack.
3. Grant a new bounded attempt batch and run workers again:

```python
import os
from pp_anchor import Engine

with Engine(os.environ["ANCHOR_DATABASE_URL"], schema="anchor_local") as engine:
    state = engine.status(run_id)
    assert state["status"] == "compensating"
    engine.retry_compensation(run_id)
```

4. Confirm every required cleanup reaches `completed`, then verify replay reports
   `compensated`. An ancestor becomes eligible only after its descendants commit success.

Do not mark cleanup complete, delete a failed task or change history with SQL. Repeating
`retry_compensation` does not clear a provider error or skip dependencies. Its three-attempt
extension applies only to failed cleanup; existing successful work is not repeated.
Backoff doubles the configured base and caps the recorded delay at one year, including
cumulative operator retry batches. A provider fence prevents late resurrection; it does
not manufacture cleanup success.

## A worker dies after an effect

An external provider may have committed even when the engine has no completion. Allow
the lease to expire and let a replacement claim a new epoch. The handler queries/retries
that same business operation. The synthetic provider returns the existing publication,
so recovery records one logical effect despite two executions. A stale process can no
longer heartbeat or acknowledge its old epoch.

For custom multi-effect workflows, derive a stable operation key such as
`f"{context.business_key}/{context.task.step}"`. Attempts/epochs identify executions
and must not become new business-operation keys. The original effect and its cleanup
must address the same operation. If a downstream system supplies neither idempotent
publication nor a cancellation fence/reversal contract, record that limitation and
reconcile manually; Anchor cannot confer those guarantees on another service.

`anchor demo --output /absolute/new/anchor-demo --seed 1729` reproduces publication,
actual process termination, reclaim and replay. Inspect `history.json` and `timeline.txt`.
The test suite also kills a process after inserting history but before projecting a
new timer: neither partial write commits, and the next epoch emits one completion.

## History or projection inconsistency

`DivergenceError` reports unknown/mixed event codecs, a definition pin mismatch,
impossible version-two transitions, missing event sequence, or a committed projection
that disagrees with history. Stop writers for the affected schema and preserve a backup
for diagnosis. Do not repair a digest, suppress the error, drop an inconvenient event
or reset the workflow status to make replay pass.

Check the binary/version used, the schema selected and backup consistency first.
Restore a coherent backup into a different empty schema, replay its runs and inspect
provider state before resuming. Keep the damaged schema for investigation. External
provider effects may need reconciliation if the backup predates a real external commit.

## Upgrade and compatibility

Definition version, event codec and snapshot archive format are separate contracts.
New runs use event codec two; existing codec-one runs continue with codec-one events
and stable command IDs. Current workers enforce causal cleanup eligibility on both.
Historical outcomes are retained; the codec does not rewrite an old out-of-order cleanup
into a different event stream.

Stop all older schedulers/workers, back up and validate the new binary before resuming.
Do not mix binary generations. Older binaries do not understand codec-two checks or
blocked cleanup. If rolling back the binary, restore its corresponding pre-upgrade
backup into a new schema and reconcile external effects; do not point it at newer state.
Changing an activity's implementation under the same registry name is also an operational
compatibility decision. The definition digest pins the name, not arbitrary Python code.

## Backup and restore

Use `anchor backup /absolute/new/snapshot.zip --schema anchor_local`. The version-one
archive streams PostgreSQL COPY under repeatable read and hashes every allowed table.
It includes engine and synthetic provider state together. Existing snapshots are never
overwritten. For a larger database than the 100 MiB snapshot bound, use PostgreSQL's
`pg_dump --schema=NAME` and an appropriate restore procedure.

Stop target workers before `anchor restore /absolute/snapshot.zip --schema NEW_EMPTY`.
All table copies commit in one transaction; a nonempty target is refused. Member
allowlists, duplicate rejection, compressed/uncompressed bounds, checksums and
non-symlink paths reject malformed archives. The existing table layout preserves
codec-one and codec-two events without changing the archive format.

After restore, replay every retained run before enabling workers. Confirm idempotent
submission identities, persisted timer behavior and provider reconciliation. Restoring
local database state cannot atomically restore an arbitrary external provider. Preserve
PostgreSQL `fsync`, `full_page_writes` and `synchronous_commit`; process-kill checks do
not simulate every storage-controller or power-loss failure.

## Owned demo cleanup

`anchor clean-demo --output /absolute/owned/path` requires a matching Anchor marker,
an allowlist of generated files and a validated `anchor_demo_*` / `anchor_bench_*`
schema. It refuses unknown files, symlinks, moved markers and shared namespaces.
Inspect outputs before cleanup. It drops only that marked schema and removes only its
known files; it never prunes Docker or drops a shared database.
