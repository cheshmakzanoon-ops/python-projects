# Run, inspect, back up, restore

Use PostgreSQL 17 or a compatible supported server. Set `MERIDIAN_DATABASE_URL` securely in the environment. `MERIDIAN_SECRET_KEY` overrides the explicitly local development-only Django key. Never publish the local key or serve Basic credentials without TLS. Start on `127.0.0.1:8104`; no third-party credentials are needed.

PostgreSQL URL query parameters are honored by Django and native snapshot connections,
including `sslmode=verify-full`, `sslrootcert`, `connect_timeout`, and `options`.
Demo schema isolation adds its search path without dropping those connection options.

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m django migrate --noinput --settings pp_meridian.config.settings
uv run --locked python -m pp_meridian.cli serve --bind 127.0.0.1:8104
uv run --locked python -m pp_meridian.cli audit --user USER_ID --tenant TENANT_UUID
uv run --locked python -m pp_meridian.cli replay --user USER_ID --tenant TENANT_UUID
```

Provision Django users and verified `Membership` rows through a trusted administrative process. Account creation is authenticated. No public signup, password reset, or production identity lifecycle is included. Application authorization does not rely on a caller's unchecked tenant body field. Operators with backup/database privileges are trusted separately from end users.

Use an owner role for migrations and a non-owner application role for table access. Ordinary runtime operations need SELECT/INSERT on journals/postings/idempotency, SELECT/INSERT/UPDATE on derived balances and mutable review state, and table-sequence USAGE. A conservative demo grant is table DML without schema ownership; immutable triggers still reject prohibited DML, as the non-owner-role test demonstrates. Never grant runtime SUPERUSER, trigger-disabling privileges, or schema ownership. End-user RLS is deliberately not claimed.

The default settings use READ COMMITTED. Tenant sequencing row locks are expected under same-tenant contention. A long-lived transaction can block all writes to that tenant. Inspect `pg_stat_activity`, `pg_locks`, transaction ages, and application latency; do not terminate production sessions without identifying the transaction owner. Only SQLSTATE 40001/40P01 is retried. A validation, overflow, or idempotency conflict is not retryable without changing the request or choosing its correct original identity.

A reconciliation run raises a validation error when a component exceeds 32 rows or 256 edges; no partial proposal publication commits. Select a smaller explicit row_ids batch; a single oversized component requires administrative review. An approval conflict means another active match already owns the row or posting; refresh the run and inspect its audit. Immutable statements with reused identities and different normalized values are rejected rather than overwritten.

Native snapshots use a consistent `pg_dump --format=custom --no-owner --no-acl` snapshot. Install a client matching the server major release, or explicitly bind `MERIDIAN_PG_CONTAINER` to a trusted running local PostgreSQL container; the helper uses its matching native tools. No arbitrary container is autodetected.

The explicit local container binding runs native tools against the container's local
socket; direct native clients use the configured database host and connection policy.
Failed dumps remove their incomplete output file so it cannot be
mistaken for a usable backup. Existing backup files are never overwritten.
Direct native clients receive their options through a temporary owner-only libpq
service file, removed when the command exits; passwords remain in the child
environment. Native service-file options containing line breaks are rejected.

```sh
uv run --locked python -m pp_meridian.cli backup --output /absolute/new-snapshot.dump
uv run --locked python -m pp_meridian.cli restore --input /absolute/new-snapshot.dump --database meridian_restore_0123456789abcdef
```

Restore only creates a fresh database named `meridian_restore_` plus 16 hexadecimal characters; existing databases are never overwritten. The role needs CREATEDB. Verify journal/posting counts, independent trial balances, and projections before using a restored database. Restoration runs in one transaction; a failed restore leaves its new empty target for inspection, with restored schema and data rolled back. Missing input files and unavailable native clients fail before creating a target. Native backup is an administrative operation over the configured database, not an end-user export. Treat backup files as sensitive outside the synthetic demo.

ME-08 tests create a previous-schema balanced fixture, migrate to current constraints, dump a live test database, restore a new database, compare history, and prove constraints remain active. They drop only their uniquely named fresh restore target in a finally block. The test role needs CREATE ROLE or an explicit preconfigured `MERIDIAN_TEST_RESTRICTED_ROLE`; CI and the local owned service provide this capability. Missing PostgreSQL/tools fail visibly.

Demo state is isolated in a random `meridian_demo_<24 hex>` schema. `clean-demo --output ABS` verifies its ownership marker and database binding, drops that exact schema, and removes only listed owned artifacts. It preserves extra user files and never deletes the normal application schema or globally prunes containers. Use the existing checkout in cloud tasks; no Git worktree is needed.

Installed wheels run without a checkout. Their generated reports hash the actual installed package and explicitly mark unavailable Git/root/lock metadata as null; checkout-based benchmark evidence carries the full revision and lock hashes. Installed outputs are not mislabeled as committed-source verification.

## Migration 0006 and publication state

Take a native backup before applying `0006_transaction_contracts`. Run migrations
with the schema owner; ordinary runtime roles should not own tables or triggers.
This migration validates the exact historical sequence prefix, counters and review decisions. An inconsistency
stops the migration atomically; it does not silently repair or discard history.

For a counter failure, inspect the affected tenant without changing it:

```sql
SELECT t.id, t.last_sequence, count(j.id) AS journal_count,
       COALESCE(min(j.sequence), 1) AS history_min,
       COALESCE(max(j.sequence), 0) AS history_max
FROM meridian_tenant t
LEFT JOIN meridian_journal j ON j.tenant_id = t.id
GROUP BY t.id
HAVING t.last_sequence <> COALESCE(max(j.sequence), 0)
    OR t.last_sequence <> count(j.id)
    OR COALESCE(min(j.sequence), 1) <> 1;
```

A count mismatch with an otherwise equal maximum can indicate an interior sequence
gap. Preserve original journal IDs/sequences and compare the known-good backup;
renumbering immutable history would change previously observed historical balances.
Do not reset the counter or bypass the migration's validation to make it pass.

For a decision failure, inspect status alongside the associated immutable records:

```sql
SELECT p.id, p.status, m.proposal_id AS matched, d.decision
FROM meridian_proposal p
LEFT JOIN meridian_approvedmatch m ON m.proposal_id = p.id
LEFT JOIN meridian_decisionaudit d ON d.proposal_id = p.id
ORDER BY p.id;
```

Pending means no match/audit; approved means one match and one approve audit;
rejected means no match and one reject audit. Preserve the backup and diagnose the
original transaction before a separately reviewed administrative repair. Do not
reset terminal statuses or synthesize audit events merely to make migration pass.

Journal publication now uses a database-private `sealed` flag. Native snapshots
retain it; restored committed journals remain closed to later appends. Applications
must not edit it. An early seal cannot make an incomplete journal valid.

The counter's deferred checks also run at commit or `SET CONSTRAINTS ... IMMEDIATE`.
`INSERT ... ON CONFLICT DO NOTHING` against an existing journal is not a supported
idempotency primitive: its before-insert allocation must roll back when no matching
journal is published. This also rejects ignored-conflict batches and a skipped
allocation followed by a successful insert in one transaction. Use the application's
idempotency key, which returns the verified existing journal before insertion.
Valid multiple-journal transactions and rolled-back savepoints retain their exact
sequence prefix; a failed commit publishes none of their facts/counter changes.

Matching
clients and runtime roles need no schema change in their public journal objects.

## Revocation, lock waits, and projection recovery

Writes retain shared locks on the user and verified membership until commit.
Revocation/deactivation can wait behind an in-flight write or a write waiting for a
tenant lock. A newly arriving write waits for an already-running revocation and then
rechecks authority. Keep transactions short and configure database statement/lock
budgets appropriate to the deployment. Inspect the actual blockers before intervening:

```sql
SELECT pid, xact_start, wait_event_type, wait_event, pg_blocking_pids(pid)
FROM pg_stat_activity
WHERE datname = current_database() AND state <> 'idle'
ORDER BY xact_start;
```

PostgreSQL `FOR SHARE` requires SELECT and UPDATE privilege on at least one column
of each locked user/membership table. A restricted runtime role can receive column
UPDATE permission on their `id` columns for locking, rather than password or authority
columns; trusted provisioning remains separate. Database credentials still represent
the trusted application, not an end user's identity.

A missing or inconsistent balance projection requires the independent audit/replay
commands above. Rebuild holds the tenant lock, folds immutable history, and replaces
projections in bounded batches. It may wait behind a posting and blocks new postings
for that tenant; unrelated tenants can continue. Re-run audit afterward. Do not replay
an external effect or submit a new business key to repair a projection.

An idempotency conflict saying the hash does not describe its journal signals cached
result corruption. Compare the original request, linked immutable journal/postings,
and known-good backup. Do not delete the key or retry under a new key: either can
conceal or duplicate the original effect. Repair belongs to a reviewed administrative
migration, with the original facts preserved.

## Bounded matching runs

A run accepts `row_ids` from the stable UUIDs returned by statement import. Select
at most 10,000 unmatched rows from one account. Omitting the field selects all
available rows only when that population fits the same budget. Duplicate, foreign,
missing, or already-consumed selections fail instead of being silently dropped.

```json
{"account_id":"ACCOUNT_UUID","row_ids":["IMPORTED_ROW_UUID"]}
```

The run also limits SQL-prefiltered postings to 50,000. Prefiltering preserves amount
and the selected date envelope; each actual edge still follows its row's seven-day
window. A budget failure publishes no run/proposals. Choose a smaller row batch;
if even a single row produces an oversized component, automatic matching cannot
resolve that scope. Keep it for an explicit administrative review rather than
truncating candidates or rewriting immutable statement references. The service has
no arbitrary date-filter endpoint or automatic fuzzy approval.

The run summary records its selected row UUIDs, eligible posting population, component
counts, exact cost, and ambiguity count. `postings` means the SQL-prefiltered population,
not every posting ever written to the account. A unique optimum is still a proposal;
only an explicit approve decision consumes identities. Rejection is terminal and
leaves both identities available to a future independently reviewed proposal.
