# Verification

## Core semantic review — October 20, 2026

The reviewed working tree passed both interpreter matrices sequentially on Linux x86_64:

| Interpreter | Tests | Additional checks |
| --- | ---: | --- |
| CPython 3.14.8 | 159 passed; no skips/xfails | Ruff format/lint, strict mypy on 23 source files, sdist/wheel build, runtime-only installed-wheel crash/restart demo |
| CPython 3.13.16 | 159 passed; no skips/xfails | Same checks in the separate compatibility environment |

Commands from the repository root:

```sh
PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check current
UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/current-3.13.16" PORTFOLIO_PYTHON=3.13.16 python scripts/portfolio.py check current
```

Both installed wheels processed 10,000 events / 10,046 admitted records, produced 25,345 latest outputs, observed deliberate child exit 73 and reported `oracle_matches: true`. The source/test/config digest is `91924a0db27061e07bd36c72669dfb4f5fedb014334b2d19ac89dc7fd82f812f`, recorded in the [focused join artifact](evidence/core-join-2026-10-20.json). The artifact names baseline commit `39d3a8d4be3e8e2e7de85379790d68f5367d6825`, marks the changed source as a working tree, and records driver/probe hashes separately. No dependency or lockfile changed. These are local checks, not a new immutable release or hosted CI result.

This pass adds 36 cases to the earlier 123-case persistence suite. Pre-fix executions reproduced premature terminal watermark advancement, stale-owner checkpoint replacement, acknowledgement leakage into an uncommitted shared-connection transaction, cancellation returning before thread settlement, unobserved mapper failures, unbounded allocation before a state check and inability to raise a recovery budget. A new online model exposed the watermark failure independently of the earlier oracle, which shared that policy mistake. The model compares every generated prefix's disposition, watermark and ordered revision/payload sequence, restores every seventh record and scans full accepted history instead of using production window/progress/index helpers.

The corrected implementation fences exact expected checkpoint bytes inside the SQLite transaction, serializes public connection operations, waits for submitted I/O on cancellation and rejects failed Engine reuse. Eight publication failure schedules verify all immutable revisions and latest results against the independent control model after actual close/reopen. Separate sink tests inject both insertion failures and terminate a real child after sink commit before journal acknowledgement, then restart across two job namespaces and reordered revisions.

Peer review additionally reproduced Python 3.14's cancelled-shield diagnostic when publication failed after cancellation, despite retrieval of its exception. Two regressions failed before the shielded task returned success/failure as data; they now verify eight repeated cancellations, settled commit/rollback prefixes, an exception cause and no loop-handler leak. Two further regressions reproduced rejection of a valid 16 KiB record at its newline and when its internal ordinal grew to two digits. Both now preserve the exact wire limit through raw replay and durable admission.

Resource tests reserve each window/join slot before allocation and cap staged output before publication; a budget-five join stops consuming candidates at the sixth attempted delivery. Operational state budgets can change on fresh recovery without changing semantic configuration or treating historical peak as current usage. The [repeatable focused comparison](BENCHMARKS.md#focused-join-comparison) measured 1.408118 s baseline versus 0.169456 s indexed median over three repetitions, with exact output checks and candidate examinations reduced from a full-scan formula of 72,006,000 to six consumed index candidates. Its process RSS rose from 22,282,240 to 23,396,352 bytes; it establishes no memory improvement or production capacity.

Checkpoint version `current-3` rejects older state because prior premature finalization can hide discarded resumed input even after every input later ends. The CLI now exports raw ingress and full saved configuration without restoring the checkpoint and supports configuration-preserving identity-pipeline replay under an explicit new job namespace. Acceptance tests exercise a checkpoint fixture tagged `current-2`, source-byte preservation, corrected late sum/revision, transform refusal and bounded import batches. The [runbook](OPERATIONS.md) gives the real commands, custom-function API path and downstream reconciliation requirements. Architecture and decision records document the terminal-progress distinction, lazy join index, transaction linearization, cancellation lifecycle and exact delivery scope.

No standard million-event workload was rerun in this pass. Historical measurements below retain their original source attribution.

## Persistence integrity review — October 20, 2026

Current's reviewed working tree passed the complete project check on Linux x86_64:

| Interpreter | Tests | Additional checks |
| --- | ---: | --- |
| CPython 3.14.8 | 123 passed | Ruff format/lint, strict mypy, sdist/wheel build, runtime-only installed-wheel demo |
| CPython 3.13.16 | 123 passed | Same checks in a separate virtual environment |

Commands, from the repository root:

```sh
PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check current
UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/current-3.13.16" PORTFOLIO_PYTHON=3.13.16 python scripts/portfolio.py check current
```

The source/test/lock digest reported by Current's `provenance()` function was `97122cdfdaeda3d0fab6b68b9362c663bf31e4923dbc8a3f3beace4cf20526ba`. This is working-tree validation, not an immutable release or hosted CI result. Dependency declarations and the lockfile did not change.

The review fixes initialization of unrelated SQLite files, unbounded negative page limits, database page-size accounting, and acceptance of inconsistent checkpoints. The initial 31 persistence-integrity cases included 30 failures against the original `da094934b37a80e03b644ec4be8aa8e697da4c49` engine/journal modules and one existing future-format rejection that already passed. A subsequent peer review added 13 cases, bringing the integrity suite to 44: missing or altered primary/unique keys, types, nullability, CHECK constraints and collations fail before any writable initialization; user triggers with names resembling SQLite internals are also rejected. Tests preserve malformed database bytes on rejection. Initial schema creation now rolls back completely on failure and can be retried; concurrent initializers create one complete format, with a bounded retry only for transient WAL-mode lock errors. The independent raw-trace oracle now checks continued processing through restoration after every generated prefix, including late revisions and retained joins.

An additional in-memory control/event exercise completed checkpoint round trips for 300 seeded multi-input traces; 100 paired concurrent empty-journal initializations also completed without duplicate format rows. These focused checks supplement the executable regression suite.

Both installed-wheel demos processed 10,000 events, produced 25,345 latest results, observed the deliberate checkpoint-boundary child exit of 73, and reported `oracle_matches: true`. Unit/integration tests include actual process termination, SQLite rollback under exhausted budgets, immutable-delivery retries, read-only inspection and safe output cleanup.

No CI or standard benchmark was rerun for this review. The historical figures below remain attached to their recorded revisions.

## Historical evidence

The [earlier reliability review](../../../docs/REVIEW.md) corrected terminal-input validation, filtered-record admission, output ownership, acknowledgement matching and replay metrics. Its Current suite had 79 tests on each required interpreter. Checkpoint code version `current-2` intentionally rejects `current-1`; controlled rebuild requirements are documented in [operations](OPERATIONS.md).

The initial committed compatibility records at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2` contain 32 tests per interpreter, quality/build checks, installed-wheel execution, demo and CI benchmark:

- [CPython 3.13.16](../../../docs/evidence/final/python313/current-3.13.16.json)
- [CPython 3.14.8](../../../docs/evidence/final/python314/current-3.14.8.json)

The [standard execution](../../../docs/evidence/final/standard/current-3.14.8.json) and [raw metrics](../../../docs/evidence/final/standard/current-3.14.8-benchmark-benchmark.json) record committed source `ec1d0106df086a48923016c33199cfbda0aebbc0`, seed 1729 and SQLite WAL/FULL durability. Separate ordinary and 50%-hot-key million-event workloads both matched the complete independent oracle. Their throughput, full-process memory cost, input hashes and repetition limits are discussed in [benchmarks](BENCHMARKS.md) and the [case study](CASE_STUDY.md).

The recorded [Current-to-Quarry integration](../../../docs/evidence/final/python314/stream-lake/integration.json) covers late revisions, duplicate delivery, historical snapshots and conflicting history at its stated source revision. Later edits do not relabel that result.

## Limits

Current requires one owner per journal and a fixed input topology. It retains ingress and immutable delivery history; finite budgets therefore bound run size. A database main-file page cap is not a filesystem quota. Batch export and independent full reconciliation require substantial memory. Tests with process exits and synchronous SQLite commits do not simulate every power-loss or storage failure. No distributed ownership, automatic checkpoint migration, arbitrary-external-effect exactly-once guarantee, or production capacity claim is made.
