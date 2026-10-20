# Verification

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
