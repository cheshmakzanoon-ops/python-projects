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

A reconciliation run raises a validation error when a component exceeds 32 rows or 256 edges; no partial proposal publication commits. Narrow input scope/date/reference or manually review statement rows. An approval conflict means another active match already owns the row or posting; refresh the run and inspect its audit. Immutable statements with reused identities and different normalized values are rejected rather than overwritten.

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
