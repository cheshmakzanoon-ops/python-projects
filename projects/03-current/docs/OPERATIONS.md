# Operations

Use a single Runtime owner per journal; SQLite serializes transactions but does not coordinate competing state-machine owners. Bind no network service: Current requires no daemon or credentials. Linux is required for the process-exit durability suite and standard RSS benchmark measurements; the library and CLI otherwise use ordinary Python/SQLite. Python 3.13 and 3.14 are required compatibility targets.

Install the default environment with `uv sync --locked --python 3.14.8`. Validate with `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, `uv run --locked mypy src`, `uv run --locked pytest --cov`, and `uv build`. For Python 3.13.16, set `UV_PROJECT_ENVIRONMENT` to a separate absolute virtualenv path and run `uv run --locked --python 3.13.16 pytest`. Keep the default `.venv` on 3.14.8; do not run different interpreters concurrently in the same virtualenv.

Run a fresh demo through the README command. `inspect --output PATH` opens an existing journal in SQLite read-only mode and prints logical keys, committed revisions, and payloads; missing or unrelated databases fail without initialization. `replay --input PATH --output FRESH_PATH` accepts newline-terminated version-one records, registers their input IDs, durably journals the given order, and prints results. Input order includes explicit watermark/idle/resume/end records; no processing-time idleness heuristic is substituted. End is terminal even for previously idle inputs. Filters do not bypass input lifecycle checks.

For a custom application, keep source offsets stable across retries. Admit records before considering them acknowledged. If admission raises after commit, retry identical records. On Runtime/checkpoint failure discard that Engine, close the journal, reopen, and recover; rerun `Runtime.run`. Never attempt to continue mutating an Engine whose apply or budget check failed. Change Config only when starting a new job, or explicitly migrate state in a separate supported migration implementation.

Opening a journal validates the format, column types/nullability, primary and unique keys, index collations, foreign keys, table flags and declared CHECK constraints before changing pragmas or creating tables. Column collations and conflict policies must also match the supported format; a case-insensitive payload column would weaken exact acknowledgement matching. Existing unrelated databases, incomplete layouts, triggers and future format versions are rejected. Only an empty database can be initialized. Schema creation and the singleton format row commit in one transaction; a failed or interrupted creation leaves an empty schema that can be retried. Concurrent initializers recheck the schema under the writer lock, and the WAL-mode transition retries only transient SQLite BUSY errors within a bounded wait budget. This does not permit concurrent Runtime owners. SQLite may create transient WAL/shared-memory sidecars while reading a WAL-mode database; rejection does not change its application schema or stored records. The main-file page budget uses the database's actual page size.

`Journal.read(after, limit)` requires a nonnegative integer cursor and a positive integer limit; `Journal.pending(limit)` also requires a positive integer limit. Booleans, fractions and SQLite's negative-limit convention are rejected rather than turning a bounded page into an unbounded read. Exhaust an iterator by advancing to the last returned ingress ordinal, not by passing a negative limit.

Checkpoint code version `current-2` rejects `current-1` state. Do not edit the saved version
string to bypass this check: older state can contain records that violated input lifecycle
rules. There is no automatic checkpoint migration. Recovery also validates registered inputs, watermark relationships, window identities and aggregates, join identities, disposition/resource counters, and the checkpoint position against retained ingress. Invalid state fails without rewriting the checkpoint. This detects inconsistent persisted state; it does not authenticate a database supplied by an untrusted party. Stop the owner and back up the original
journal before rebuilding anything.

For a controlled rebuild, retain the original complete `Config`, `job_id`, mapper,
predicate, and `pipeline_version` from the application deployment. Read the unchanged raw
ingress in ordinal order with `Journal(old_path, read_only=True).read(...)`, admit it into
a **new** journal, and initialize that journal with
`new_journal.recover(original_config, job_id=original_job_id)`. Supply the original mapper
and predicate to its `Runtime`, and retain suitable journal/state budgets. The `replay` CLI
uses default window/lateness settings, an identity pipeline, and job `demo`; it is for its
documented default pipeline, **not a general checkpoint migration command**.

Reconcile the rebuilt outputs independently before resuming delivery. If retained ingress
contains newly rejected events after end, unregistered inputs, or events while idle, stop
and resolve that history explicitly; retrying or dropping records silently is not a
migration. Corrected results may also require explicit reconciliation with an existing
external sink's immutable delivery identities and revisions. Preserve the original
journal and sink state until that reconciliation is complete.

The local sink is already published with the checkpoint. For external delivery, repeatedly read `Journal.pending(limit)`, call `IdempotentSink.put(delivery)`, then `Journal.acknowledge(delivery)`. Acknowledgements must match both the registered identity and canonical payload; unknown or conflicting acknowledgements fail without marking a row sent. Never acknowledge before sink commit. A sink outage fills the finite outbox budget; publication then raises BudgetExceeded and leaves the previous checkpoint valid. Drain the sink and recover/retry. Set durable admission/state budgets for the workload; never drop accepted events to maintain a throughput measurement.

Stop the owner before a filesystem backup. For an online SQLite-safe backup, use Python sqlite3's `Connection.backup` API into a new destination, or stop the process and run SQLite `.backup`. Do not copy only the main file while a live WAL may contain committed data. Keep the code/config version with the backup. Restore into a fresh path, recover with identical Config, and replay the suffix from the restored ingress table. Tests reopen process-killed databases and verify the precise committed prefix.

`clean-demo --output PATH` only accepts a directory bearing the exact regular `.current-owned-demo` marker and rejects symlink roots, ancestors and markers. It removes that explicitly selected owned demo directory, including its database. Keep personal files outside owned demo directories. Demo, replay and benchmark require fresh output directories containing at most the ownership marker; existing generated files or symlinks cause failure before opening a database or writing reports. These are local caller-selected directories, not a boundary against another process concurrently replacing paths. No global reset, Docker prune, or outside-directory deletion is used.

Standard benchmarks require an exclusive resource lease and significant transient disk/memory for a million journaled events plus independent reconciliation. Each measured standard run removes its marked bulk directory after saving a compact report; generator, seed, profile, source hash, configuration, and metrics remain. CI retains full small outputs. Retry with a fresh benchmark directory after interruption; cleanup requires the top-level ownership marker.
