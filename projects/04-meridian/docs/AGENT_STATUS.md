# A04 Meridian handoff

Status: verified at immutable source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`.
Meridian implementation, accepted matrix verification, and full standard measurement are complete.
The coordinator owns final repository integration and publication. Implementation writes remain paused.

Accepted [Python 3.13 evidence](../../../docs/evidence/final/python313/meridian-3.13.16.json)
and [Python 3.14 evidence](../../../docs/evidence/final/python314/meridian-3.14.8.json)
both passed, including 46 tests per interpreter. The [standard wrapper](../../../docs/evidence/final/standard/meridian-3.14.8.json)
and [raw report](../../../docs/evidence/final/standard/meridian-3.14.8-benchmark-benchmark.json)
passed against the same clean immutable source. Earlier development checkpoints below are historical.

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
the completed accepted immutable measurement is summarized at the end of this status record.

The earlier independent-review, immutable-evidence, and standard-measurement gates are now closed
by the accepted final evidence linked above. No project implementation acceptance IDs remain open.
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

## Workload failure propagation review

Status: targeted fix verified; implementation writes paused. Demo/benchmark status and CLI
exit now reflect all mandatory checks. Failed reports retain failed_checks plus actual audit
and reimport diagnostics. Benchmark reimports compare ordered identities, distinct counts,
and stored before/after row counts; public ci=1000 and standard=250000 journal dimensions
are unchanged. Tests reduce only private ci fixture dimensions and assert actual report
parameters; they are not advertised as full-profile benchmark evidence.

Six targeted real-PostgreSQL CLI regressions passed on Python 3.14.8 (13.45 s) and 3.13.16
(15.85 s): inconsistent independent audit; mismatched repeated-import identity; unexpected
persisted statement row; normal passing benchmark; failed demo rebuild; mismatched duplicate
journal response. Initial duplicate-response test adapter lacked Client's json method; corrected
the response-shaped injected fixture, then reran all six successfully. Test connection-lifetime
mutation is restored between fixtures to prevent cross-test client-session leaks.

Commands: `uv run --locked pytest tests/acceptance/test_workload_failure_reporting.py -q`
with separate MERIDIAN_TEST_DB_NAME per interpreter; explicit 3.13 environment uses
`UV_PROJECT_ENVIRONMENT=/workspace/.cache/meridian-py313` and `--python 3.13.16`.
Ruff format/check (53 files), strict mypy (33 modules), and sdist/wheel build pass.
No heavy benchmark or full-suite repetition ran during that focused fix. The coordinator subsequently
verified both full suites, public ci workloads, and the standard profile at the accepted immutable revision.

## Accepted final standard result

The clean CPython 3.14.8 standard run at `59443e2bcdfc6a1dd81f8334c108474eef2d3030`
measured 250000 journals / 1000000 postings, eight clients, 100 tenants, and 100000 statement rows.
There was one full cost-exception measurement plus one additional two-posting warmup journal.
The same-tenant phase measured 83.5906 journals/second (125000 journals; p95 0.168624 s);
the many-tenant phase measured 108.9654 journals/second (125000; p95 0.126260 s).
Independent replay took 23.4057 s. Matching accounted for 99000 matched / 1000 unmatched rows
and 1000 ambiguous components. Reimport returned 100000 stable identities and preserved 100000
stored rows. All mandatory checks passed; audit/reimport failure lists were empty.

The [account distribution observation](../../../docs/evidence/final/meridian-account-distribution.json)
records 10000 provisioned accounts but only 496 with postings. This is a hot-account workload,
not evidence that all 10000 accounts were actively written. Zero batch-boundary wait samples
must not be read as zero contention: the [during-run observation](../../../docs/evidence/final/meridian-lock-observation.json)
shows seven waiting sessions. That snapshot supplies neither cumulative wait time nor an
independent acceptance pass. Single-run synthetic timing does not establish production capacity.

Exact raw-report source SHA-256: `530ea3216de80d90015a655209261085f6f6b2d1ec1fde92e5dce8cfd22dcd51`;
lock SHA-256: `278057ae9b5d37f8ac2d66073891b25e2d51b15d13f7f753129aea59e01bb54d`.
The raw report and wrapper retain their distinct declared digest input scopes. No source,
dependency, test, or evidence file changed during this documentation-only handoff.
