# Meridian verification

Verification reports identify the source they exercised. Historical measurements below
remain tied to their recorded revisions; they are not performance results for later changes.
No hosted CI or public deployment result is inferred from local execution.

## Current maintenance review

The current review hardens the HTTP boundary without changing ledger transactions,
PostgreSQL migrations, accounting semantics, or the dependency lock:

- Reject duplicate JSON members, non-finite numbers, invalid Unicode, null characters,
  bodies over 1 MB, and containers nested beyond 32 levels. Malformed input returns
  a validation error before persistence, including inputs that exhaust parser recursion.
- Bound pagination offsets to PostgreSQL's signed 64-bit range and advertise allowed
  methods in `Allow` response headers.
- Return operator-view errors as plain text, preventing query validation messages from
  becoming executable HTML. Authenticated responses use `Cache-Control: no-store`;
  record pages restrict scripts, embedding, forms, and external resources with CSP.
- Present journals, account history, and reconciliation proposals as escaped, responsive
  tables with keyboard navigation, explicit units, ambiguity labels, and bounded pagination.

Commands run from `projects/04-meridian` use uv 0.12.23, the committed lock,
`UV_CACHE_DIR=/workspace/.cache/uv`, and `UV_PYTHON_INSTALL_DIR=/workspace/.python`.
Database tests require real PostgreSQL 17 and matching native tools. The explicit local
container binding is `MERIDIAN_PG_CONTAINER=pp-meridian-dev`; connection values belong in
the environment. Interpreters use separate environments and test database names.

Local validation on Python 3.13.16 passed **94 tests**, Ruff formatting and lint,
strict mypy (35 source files), source/wheel builds, and the external installed-wheel
PostgreSQL demo. Python 3.14.8 passed the complete suite and the same package checks;
its installed-wheel demo returned `status: passed` with no failed checks.
Django's system check reported no issues. The repository [verification index](../../../docs/STATUS.md) tracks subsequent
committed-source checks. Focused HTTP tests exercise invalid inputs without writes, tenant-scoped views,
HTML escaping, cache policy, CSP, and pagination. Full suites retain concurrency, direct SQL
constraints, migration, native backup/restore, crash rollback, and public demo/cleanup checks.
No full standard benchmark is rerun for this maintenance change.

## Historical accepted matrix

The [Python 3.13 report](../../../docs/evidence/final/python313/meridian-3.13.16.json)
and [Python 3.14 report](../../../docs/evidence/final/python314/meridian-3.14.8.json)
record **46 tests per interpreter** at immutable source
`59443e2bcdfc6a1dd81f8334c108474eef2d3030`, including installed-wheel execution.
The subsequent October 18 correctness review recorded **59 tests per interpreter**
against real PostgreSQL, covering transport-option preservation, failed native restore
rollback, missing-input handling, and UTC/date-boundary validation.

ME-01 through ME-08 map to their executable checks in [acceptance](ACCEPTANCE.md).
No required PostgreSQL check is replaced with a service-dependent skip or expected failure.
Native backup/restore and non-owner constraint tests require the privileges described in
[operations](OPERATIONS.md). Passing local tests does not establish a remote TLS handshake,
regulatory compliance, or production identity management.

## Historical standard workload

The [standard verification wrapper](../../../docs/evidence/final/standard/meridian-3.14.8.json)
and [raw report](../../../docs/evidence/final/standard/meridian-3.14.8-benchmark-benchmark.json)
refer to the same clean source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`.
They measured 250,000 journals and 1,000,000 postings with eight clients, 100 tenants,
and 100,000 statement rows. One additional two-posting journal was the warmup.

The same-tenant phase measured 83.5906 journals/second with 0.168624-second p95 latency;
the many-tenant phase measured 108.9654 journals/second with 0.126260-second p95.
Independent replay took 23.4057 seconds. Matching reported 99,000 matched and 1,000
unmatched rows across 1,000 ambiguous components. Reimport preserved all 100,000
identities and stored rows. The mandatory audit and reimport checks passed.

The [account distribution observation](../../../docs/evidence/final/meridian-account-distribution.json)
found only 496 active accounts among 10,000 provisioned accounts. The
[during-run lock observation](../../../docs/evidence/final/meridian-lock-observation.json)
found seven waiting sessions even though batch-boundary samples reported zero.
This is one synthetic hot-account measurement, not evidence of production capacity,
absence of contention, or low variance. See [benchmark methodology](BENCHMARKS.md).
