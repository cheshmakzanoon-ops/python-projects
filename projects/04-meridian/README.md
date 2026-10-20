# Meridian

A multi-tenant double-entry ledger and statement reconciliation service for a fictional equipment-rental business. Integer money, immutable postings, commit-ordered history, explicit reconciliation review, and independent projection rebuilds are the product's central contracts.

Python 3.13 / 3.14, Django 5.2 LTS, PostgreSQL 17, psycopg 3. No real banking connections or payment execution.

```sh
uv sync --locked --python 3.14.8
export MERIDIAN_DATABASE_URL='postgresql://USER@127.0.0.1:5432/DATABASE'
uv run --locked python -m django migrate --settings pp_meridian.config.settings
uv run --locked python -m pp_meridian.cli demo --output /tmp/meridian-demo --seed 1729
uv run --locked python -m pp_meridian.cli benchmark --profile ci --output /tmp/meridian-ci --seed 1729
uv run --locked python -m pp_meridian.cli serve --bind 127.0.0.1:8104
```

The demo and benchmark create a separately owned schema, migrate it, and write provenance-bearing JSON plus a small HTML demo report. Their database role needs CREATE SCHEMA; ordinary application roles only need table access. They refuse nonempty foreign output directories and source-tree outputs. Reuse an output directory only after `clean-demo --output ABSOLUTE_PATH`, which removes that demo's named schema and owned artifacts while preserving unrelated files. Application data in the normal schema is never reset by demo cleanup.

The demonstration submits an invoice through the authenticated API, resubmits it, posts a payment/refund and a CAD journal, reverses the invoice, races eight transfers, reviews an ambiguous statement match, deliberately corrupts a derived projection, and repairs it by independent replay.

Every JSON endpoint requires HTTP Basic authentication using a Django user, `X-Tenant-ID`, and verified active membership. POST journals/reversals also require `Idempotency-Key`. Use TLS beyond loopback. Session cookies are not accepted as API authority. Create users/memberships through Django administrative provisioning; the demo creates only a visibly synthetic local operator in its isolated schema.

```json
{"currency":"USD","reference":"invoice-100","postings":[{"account_id":"ACCOUNT_UUID","amount":"100.00"},{"account_id":"OFFSET_UUID","amount":"-100.00"}]}
```

The API returns journal/posting identities and integer minor units. Focused record views show journal postings, ordered account history, and reconciliation proposals as responsive tables with explicit currency units and ambiguity markers. They require the same authentication and tenant headers as the API.

Read [API](docs/API.md), [verification](docs/VERIFICATION.md), [architecture](docs/ARCHITECTURE.md), [acceptance](docs/ACCEPTANCE.md), [operations](docs/OPERATIONS.md), and [benchmarks](docs/BENCHMARKS.md). No claim of regulatory compliance or production banking suitability is made.

```sh
MERIDIAN_PG_CONTAINER=your-explicit-local-postgres-container uv run --locked pytest
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv build
```

Native snapshot tests require matching `pg_dump`/`pg_restore` clients or the explicit container binding. They do not skip missing PostgreSQL. The database test role must create a temporary database and provision or use a non-owner constraint-test role. See operations for restricted-role deployments.
