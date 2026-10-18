# Operations

Use a dedicated PostgreSQL database and caller-selected schema. Never reuse Meridian's
namespace. Set `ANCHOR_DATABASE_URL` in your shell/environment settings; values are not
written to histories, reports, or logs. Default schema is `anchor`, tests generate
`anchor_test_*`, and owned CLI outputs use `anchor_demo_*` / `anchor_bench_*`.

Install with `uv sync --locked --python 3.13.16`. Run `anchor scheduler`,
`anchor worker --concurrency 4`, and optionally `anchor serve --port 8101` in separate
terminals (or use `uv run --locked python -m pp_anchor.cli` in place of `anchor`).
Worker and scheduler are foreground processes; interrupt them to stop. Database rows
survive interruption. A process killed with a live lease becomes reclaimable only when
the database deadline expires. Never reduce a lease below the expected heartbeat latency.

`anchor inspect RUN_ID`, `anchor replay RUN_ID`, `GET /runs/RUN_ID`, and paginated
`GET /runs/RUN_ID/history?after=0&limit=100` expose state. Health means the process is
alive; readiness executes a database query. Neither endpoint promises worker capacity.
Structured history records carry run, command, attempt, epoch, selected retry delay,
error, result and sequence. `Engine.metrics()` reports run/task states, attempts,
queue delay and owned schema database bytes.

A `compensating` workflow with failed cleanup is not successfully cancelled. Inspect its
history, repair the external cause, then call `engine.retry_compensation(run_id)` and
run workers again. This preserves the original failed attempt and admits bounded new
attempts. Do not manually mark cleanup complete. The synthetic provider's terminal fence
rejects late publication even before cleanup succeeds.

Back up engine and provider state together with `anchor backup /absolute/new/snapshot.zip
--schema NAME`. This version-one snapshot streams PostgreSQL COPY under a repeatable-read
snapshot and records SHA-256 hashes for every whitelisted table. Restore using
`anchor restore /absolute/snapshot.zip --schema EMPTY_TARGET`. The target must be empty;
all table copies commit in one transaction. Existing snapshots are never overwritten.
Archive member allowlists, duplicate-member rejection, compressed/uncompressed size bounds,
checksums and non-symlink paths reject malformed/path-traversal inputs before restoration.
The required integration test backs up real PostgreSQL state, restores to a new schema,
verifies histories/idempotency, then fires the restored persisted timer once. It also
rejects corruption, traversal and nonempty targets. Snapshots are bounded to 100 MiB;
use PostgreSQL `pg_dump --schema=NAME`/`pg_restore` for larger databases. Provider and engine
must share the backup boundary or an external consistency procedure. No snapshot can
coordinate an arbitrary external provider automatically.

`anchor clean-demo --output /absolute/owned/path` accepts only a matching Anchor marker
and a known allowlist of generated files. It drops exactly the marker's validated demo
schema and deletes only those files. Symlink paths, unknown files, missing/moved markers,
and non-demo schemas are rejected. It never prunes Docker or drops a shared database.
Unknown files must be moved by the caller before resetting; do not weaken ownership checks.

Failure diagnostics: missing URL fails explicitly; refusal/auth errors require the actual
service and credentials; `StaleLeaseError` means the worker must discard its result;
`DivergenceError` names the incompatible history event. PostgreSQL must retain fsync,
full_page_writes and synchronous_commit for the documented durability boundary. SIGKILL
checks cover process failure, not all power-loss/storage-controller failures.
