# Meridian verification

Verification reports identify the source they exercised. Historical measurements below
remain tied to their recorded revisions; they are not performance results for later changes.
No hosted CI or public deployment result is inferred from local execution.

## Sequence publication peer review — 2026-10-20

A fresh PostgreSQL reproduction found that `INSERT ... ON CONFLICT DO NOTHING`
ran journal sequence allocation before suppressing the duplicate row. It committed
counter 2 with only journal sequence 1; the next ordinary post then received sequence
3. An ignored insert followed by a real insert in one transaction could hide the
gap from a final counter/maximum comparison. This was an additional defect after
the core review below, not evidence that the immediate counter guard was sufficient.

Four regression cases failed before the correction: an ignored insert alone,
ignored then successful insertion, an ORM ignored-conflict batch, and migration of
legacy sequences `[1, 3]` whose counter and maximum both equal three. Two positive
cases retain multiple journals before first commit and valid savepoint rollback
with an explicit deferred-constraint flush. The corrected migration validates
legacy prefix counts/bounds once and checks every new allocation with the existing
tenant/sequence index at commit. It also checks the final current counter/maximum;
no full-history scan was added to each posting.

The corrected working tree passed **120 tests on each interpreter**: CPython
3.14.8 in 37.42 seconds and isolated CPython 3.13.16 in 38.44 seconds, with no
skips or expected failures. Both complete dispatcher checks also passed Ruff,
strict mypy on 36 source files, source/wheel builds and external runtime-only
installed-wheel demonstrations. The full suites include real PostgreSQL contention,
migration reversal/reapplication and native backup/restore. Commands from the
repository root were `PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check meridian`
and the same check with `PORTFOLIO_PYTHON=3.13.16` and its separate
`UV_PROJECT_ENVIRONMENT`; each used a distinct synthetic test database.

The final source/test/benchmark/config digest is
`2df2aa1894aa609c9d44adb136dee68e1d0a56efafe5070f2258d7591b0f19ee`
under `pp_meridian.evidence.provenance()`'s stated input scope. These are local
working-tree checks; no new performance claim is made. The 114-case results below
describe the preceding core pass, and its workload artifact retains its original
source attribution.

## Core transaction review — 2026-10-20

The deeper review starts from baseline `39d3a8d4be3e8e2e7de85379790d68f5367d6825`. Seven new real-PostgreSQL
regressions failed before the fixes: savepoint-created journals rejected their own
transaction's postings; a forged same-tenant idempotency cache returned a different
journal; an approved status committed without match/audit; rejected proposals
reopened; published proposals deleted; the tenant sequencing counter was rewritten;
and membership revocation committed ahead of an already authorized posting.
An isolated legacy-schema reproduction committed sequences 1, 10, then 2 after counter
rewrites: an already observed `as_of_sequence=2` balance changed from 100 to 125 after
the later posting. The counter guard prevents that historical-prefix corruption.
A subsequent focused reproduction also showed that the existing proposal identity
trigger allowed a pending published proposal's primary UUID to change. Migration
0006 now freezes that key as well as the run/row/posting/ambiguity fields.

Migration `0006_transaction_contracts` replaces tuple-XID append protection with
monotonic journal sealing, guards the sequencing counter, and couples terminal
proposal status to one match/audit decision at commit. The application reserves
active-user/membership authority through write commit and verifies cached results
against immutable facts. Projection replay streams facts and repairs bounded UPSERT
batches under the tenant lock. Matching preparation has whole-scope population
budgets and an explicit row UUID selection interface.

Additional real contention checks cover user deactivation, independent-tenant
concurrency by one principal, rebuild versus queued posting, and concurrent approvals.
Migration tests reject inconsistent legacy counters/decisions rather than silently
accepting them. Publication checks cover savepoints, prohibited reopening, and an
early seal that cannot bypass journal conservation.

An independent enumerator checks all feasible partial assignments for **400 sparse
1×1 through 4×4 graphs**, seed **61783**, including zero unmatched cost, isolated rows,
alternative optima, and reordered inputs. It compares the exact optimal pair sets,
minimum cost, and ambiguity result. No matching-solver defect was found in that
exercise. Dense Hypothesis/exhaustive checks remain in the ordinary suite.

The final core suite passed **114 tests on each interpreter**: Python 3.14.8 in
36.63 seconds and Python 3.13.16 in 35.17 seconds, without skips or expected failures.
Ruff formatting/lint, strict mypy (36 source files), migration-state checks, and
source/wheel builds passed on both versions. External runtime-only wheel demonstrations
also passed. These are local working-tree results; final committed-source checks
are recorded separately. Historical performance evidence below is unchanged.

A [public CI-sized contention run](../artifacts/core-review-ci-2026-10-20.json)
passed on Python 3.14.8, seed 1729: 1,000 journals, 4,000 postings, 200 accounts,
four tenants, 500 statement rows, and eight concurrent clients. Independent replay,
row accounting, controlled ambiguity, and stable reimport all passed. Same-tenant
throughput was 152.85 journals/second; many-tenant throughput was 248.74. This is a
concurrent-development measurement with `source_dirty=true`, not a before/after
performance comparison or a claim about production capacity. This workload preceded the final proposal-primary-key guard; its recorded source content
SHA-256 is `f6e8a7454722e0449b14d19ec478f8c0b58a37e24de36ae96a150d55612b07fb`.
The authenticated row-selection API also returned 201 with the exact selected UUID;
a duplicate selection returned 400. These functional checks are separate from the
benchmark's matching measurements.

## Earlier interface maintenance review

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
