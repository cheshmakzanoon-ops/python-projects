# A04 Meridian handoff

Status: verifying (implementation and local gates complete; coordinator independent review,
immutable committed-source evidence, and full standard measurement remain).

ME-01–08 are implemented and locally verified on real PostgreSQL 17.11. No required test
uses skips/xfails or mocks PostgreSQL. Exact commands below all exited 0:

- `uv run --locked pytest --cov=pp_meridian.domain --cov=pp_meridian.reconciliation --cov=pp_meridian.application --cov-branch --cov-report=term-missing -q`: 40 passed on CPython 3.13.16, 96% combined own-core coverage; application ledger 91%, reconciliation 91%, domain 100%, assignment 97%, candidates 99%, normalization 100%.
- Python 3.14.8 in independent UV_PROJECT_ENVIRONMENT: 40 passed.
- `uv run --locked ruff format --check .`: 52 Python files formatted; `ruff check .`: passed.
- `uv run --locked mypy src`: strict, 33 source modules passed.
- `uv build`: sdist and wheel passed; clean external wheel install imported resources/core and ran the full PostgreSQL CLI demo from /tmp successfully.
- Authenticated API demo: /workspace/.results/meridian-demo-final-dev/{demo.json,report.html}.
- CI workload: /workspace/.results/meridian-benchmark-ci-v2/benchmark.json: 1000 measured 4-posting journals, 200 accounts, 500 rows, eight clients, five batches per contention mode; 63.2 same-tenant journals/s and 132.4 many-tenant journals/s under shared-machine load; five controlled ambiguous components/five unmatched rows; independent replay and stable reimport pass. One warmup journal is additional.
- Native snapshot/restore, previous-fixture migration, non-owner constraints, killed-process rollback,
  real SQLSTATE40001 full-transaction retry, and explicit commit-order lock test all passed.

Real DB tests use coordinator-supplied MERIDIAN_DATABASE_URL and
MERIDIAN_PG_CONTAINER=pp-meridian-dev locally. Credential values are not saved here.
Django 5.2.18, psycopg 3.3.6, uv 0.12.23. Python default is now 3.14.8 (coordinator-selected); 3.13.16 remains validated.

Most serious discovered defects: SQL OLD trigger-alias collision fixed with incremental
migration; exhaustive oracle exposed additive unmatched-edge ambiguity, now a fixed regression;
concurrent direct SQL account mutation required SHARE rather than KEY SHARE; independent
missing-projection audit/rebuild and outer transaction ownership now protect acknowledgement.
Sparse component adjacency avoids quadratic rescanning. Persistent benchmark clients and a
single parameterized projection UPDATE reduce connection/roundtrip overhead without bypassing
production constraints.

Public API: Basic Django authentication, verified X-Tenant-ID, Idempotency-Key; decimal-string
journal postings, immutable history/reversal, historical balance, statement import, run/proposal
review. Default loopback port 8104. Standard profile retains 250000 journals/~million postings,
10000 accounts/100 tenants/100000 rows, one costly full measurement per contention mode;
coordinator will run from a stable committed tree under an exclusive resource lease.

Current exact remaining: coordinator independent review, final immutable source evidence,
full standard profile measurement. No missing implementation acceptance IDs are known.
No shared/root or Git mutations performed. Root CI/container binding request acknowledged.

Final expanded acceptance test also executes the public demo and clean-demo subprocesses,
verifies the exact owned PostgreSQL schema is dropped, and preserves a caller-created file.
Implementation writes are paused for coordinator review/handoff.

Independent A03 review findings reproduced and fixed: cross-tenant idempotency poisoning
(composite tenant/journal FK plus defensive cached-return check), statement/run-only account
identity relocation (history guards plus shared account insertion locks), and large-cost
solver sentinel collision (exact integer/unreachable distances). Migration 0005 rejects
legacy inconsistent cache/statement/proposal history. Raw SQL, legacy migration/authorization,
concurrent application/direct first import versus tenant/currency changes, immutable run and
proposal identity tests all pass. Final expanded result: 40 passed Python 3.13.16 and 40 passed
Python 3.14.8; own-core coverage96%, ledger91%. Wheel rebuilt/reinstalled and full PG demo
from /tmp passed at /workspace/.results/meridian-installed-wheel-review-fixes-v2/report.html.
Implementation writes are paused again for coordinator review/commit.
