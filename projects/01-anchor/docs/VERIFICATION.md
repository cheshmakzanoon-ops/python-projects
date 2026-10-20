# Verification records

## Current core verification

The transaction/rollback implementation is described in [architecture](ARCHITECTURE.md)
and its [design decisions](DECISIONS.md), with operational recovery examples in the
[runbook](OPERATIONS.md). The four initial regression tests failed on the preceding
implementation; the rest of the new coverage checks additional invariants rather than
claiming four defects per test count. The suite includes a 60-example independent DAG
oracle and real PostgreSQL/SIGKILL transaction recovery.

| Interpreter | Python tests | Format/lint/strict types | Build/installed-wheel recovery |
| --- | ---: | --- | --- |
| 3.14.8 | 131 passed in 12.31 s | passed, 25 source files | passed |
| 3.13.16 | 131 passed in 12.10 s | passed, 25 source files | passed |

No skips or expected failures conceal missing services. One upstream Starlette/httpx
warning remains. The bounded [scheduler diagnostic](BENCHMARKS.md#scheduler-transaction-diagnostic)
verified one history read and exact timer completion at widths 32–1,000. Its report
retains actual dirty-source provenance; earlier workloads below remain historical.


## Reliability and interface review — 2026-10-20

The current review adds bounded SQL history pagination and replaces private request-body
mutation with a typed ASGI middleware. Body framing tests cover chunked delivery,
oversize declarations, duplicate and malformed Content-Length, mismatched lengths,
client disconnects and non-HTTP scopes. HTTP request models reject unknown fields.
Submission and signal parsing now rejects duplicate JSON members, non-finite values,
null characters, unpaired Unicode surrogates, and more than 64 container levels.
An iterative validator protects SDK canonicalization too. NUL/surrogate payloads
and 2,000-container HTTP bodies previously returned `500`; they now return `422`
without persisted runs or signals. GET health checks retain their original semantics.

Lease durations and injected timer offsets now reject NaN, infinity, booleans and
out-of-range values before database state changes. Definition versions match PostgreSQL's
positive 32-bit integer range. Exponential retry delay is capped at one year. Without
that cap, a valid 32-attempt definition with a one-year base delay raises PostgreSQL
`DatetimeFieldOverflow` on attempt 20; the failure was reproduced against source
`da094934b37a80e03b644ec4be8aa8e697da4c49`. Its regression exercises all 32 attempts,
checks each recorded delay and confirms the final failed workflow state.

With a real local PostgreSQL 17 service, **111 tests passed on CPython 3.14.8**
(10.17 seconds) and **111 passed on CPython 3.13.16** (10.50 seconds), with no skips
or expected failures. These suites include process termination, stale-worker fencing,
backup/restore and the full recovery CLI demonstration. Ruff formatting/lint, strict
mypy over 23 source files, and wheel/sdist builds also passed on both interpreters.
Runtime-only wheel installations outside the source tree completed the export, actual
worker termination, recovery, replay and owned cleanup on both versions.

Commands from `projects/01-anchor`: `uv sync --locked --python VERSION`,
`uv run --locked --python VERSION ruff format --check .`, `ruff check .`,
`mypy src`, `pytest`, and `uv build --python VERSION`. The 3.13 environment uses
`UV_PROJECT_ENVIRONMENT=/workspace/python-projects/.local/venvs/anchor-3.13.16`;
checks run sequentially because build output is shared.

One upstream Starlette/httpx test-client deprecation warning remains. Heavy benchmark
profiles and the cross-product settlement demonstration are separate checks; older
measurements below retain their original source identity. These working-tree checks
do not claim hosted CI success or a newly measured throughput improvement.


## Code review addendum — 2026-10-18

This earlier review fixed three correctness issues:

- An empty error string incorrectly completed an exhausted activity. Failure detection now
  consistently checks whether an error was supplied, including compensation transitions.
- Oversized or non-finite activity results escaped the worker and left the task leased.
  Shared result validation now runs at the handler boundary so these failures enter the
  existing bounded retry policy. Direct engine acknowledgements retain the same validation.
- Long chains of internal joins recursively appended and replayed history. Internal events
  now use an explicit stack and one transaction-locked reducer state, retaining the existing
  depth-first event order and atomic projection updates.

Six regression cases cover empty errors, oversized/NaN results with and without heartbeats,
and all 1,000 supported steps in an internal join chain. The five error/result cases failed
against the previous implementation before the fixes. Full PostgreSQL suites pass on
Python 3.13.16 (**60 passed in 8.47 s**) and 3.14.8 (**60 passed in 9.22 s**), including
process-failure, cancellation/fencing, snapshots, and the CLI recovery demonstration.
Ruff formatting/lint and strict mypy pass on both interpreters; wheel and sdist build pass.
Commands: `python -m pytest -q --tb=short`, `ruff format --check .`, `ruff check .`,
`mypy src`, and `uv build --out-dir /workspace/python-projects/.local/review-builds/anchor`.
Tests used a real local PostgreSQL service through ANCHOR_DATABASE_URL.

The locked Starlette/httpx test-client integration emits one upstream deprecation warning.
Heavy benchmarks and the cross-project settlement integration were not rerun in this
review. The immutable records below describe their original source revisions; they do not
verify these working-tree changes. These records apply to the reviewed source revision and do not certify later changes.

## Previous accepted verification

AN-01–AN-08, immutable compatibility checks, installed-wheel demonstrations, ci profiles,
the full standard workload, and the settlement integration have passed. The default is
CPython **3.14.8**, with **3.13.16** also required and verified. Repository synchronization and hosted CI observations are reported separately from local tests.

## Accepted immutable verification

The [compatibility matrix](../../../docs/evidence/README.md) and
[machine-readable counts](../../../docs/evidence/final/compatibility-counts.json) link the
accepted results. Both interpreter records tested clean exported source
`7114e39c7e9e8af177e84fe8cd990fe5a09bde63` and confirmed unchanged inputs afterward:

| Interpreter | Required tests | Check, demo, ci benchmark, cleanup |
| --- | ---: | --- |
| 3.13.16 | 54 passed in 15.82 s | [accepted wrapper](../../../docs/evidence/final/python313/anchor-3.13.16.json) |
| 3.14.8 | 54 passed in 16.20 s | [accepted wrapper](../../../docs/evidence/final/python314/anchor-3.14.8.json) |

The check logs include locked installation, Ruff formatting/lint, strict mypy, real
PostgreSQL/process tests, wheel/sdist build, runtime-only wheel installation, and a complete
installed-wheel demo outside source. Both ci benchmarks passed five measured repetitions;
the raw results are linked in BENCHMARKS.md. The accepted wrapper project digest is
`6efba1556543a98b8c0a36ff990d085569902ad50849b21bedd679fbf5f8e2f7`, with lock digest
`cb58668e71ccbc29112a367ef6cd358115039a96bffa666ba83c402e7929fdac`.

The full standard run passed on clean source
`59443e2bcdfc6a1dd81f8334c108474eef2d3030`, with the same wrapper project/lock digests:
[accepted wrapper](../../../docs/evidence/final/standard/anchor-3.14.8.json) and
[raw measurement](../../../docs/evidence/final/standard/anchor-3.14.8-benchmark-benchmark.json).
It completed all 5,000 accepted workflows, 25,000 logical activities and 25,250 attempts,
including 250 injected retries, with no orphan tasks. BENCHMARKS.md records timings,
backlog interpretation and the explicit one-full-measurement exception.

[IN-01 settlement](../../../docs/evidence/final/python314/settlement/integration.json)
passed committed source `7114e39`; its
[Anchor evidence](../../../docs/evidence/final/python314/settlement/anchor-evidence.json)
records a worker killed after the ledger commit, retry returning the same journal,
and a later failed workflow successfully compensated through Meridian's public interface.

## Implemented contracts and acceptance

AN-01 deterministic replay/command diagnostics; AN-02 submission SIGKILL before/after
commit plus concurrent canonical idempotency; AN-03 SIGKILL after provider effect before
ack; AN-04 epochs/expired heartbeat plus resumed real stale process; AN-05 persisted timers
on restart with two schedulers and injected timer clock; AN-06 every join order, early and
duplicate signals, cancellation/completion races and resumed pre-effect worker fencing;
AN-07 exhausted failed cleanup remains unresolved until explicit successful retry; AN-08
two schedulers/adapters and six worker slots account for all flaky accepted runs with no
orphan task. See ACCEPTANCE.md and the accepted check logs for the corresponding tests.

Additional controls include bounded definition/payload/result validation, bounded admission
with HTTP 429, bounded request bodies, paginated history, checksummed repeatable-read
snapshot backup and atomic empty-target restore, path/symlink safeguards, provider payload
conflict detection, and preserved asyncio cancellation. The installed CLI independently
verifies all 60 exported CSV rows, recovery, replay and owned cleanup.

## Historical development evidence and limits

`artifacts/development-verification.json`, `development-demo-*` and
`development-baseline-ci.json` remain authentic historical captures. Development core
coverage measured 96.35% combined and 202/216 branches (93.5%); its source scope and
post-check capture timing are recorded. These captures do not replace the accepted clean,
immutable records above. Raw benchmark and outer verification hashes use their respective
recorded input scopes; their different digest values are retained without rewriting evidence.

No Anchor local acceptance or standard-workload gate remains open. Hosted CI status must be checked independently of these local records. Linux is required for SIGKILL
process tests, and the PostgreSQL URL is supplied through ANCHOR_DATABASE_URL without
saving credential values. No arbitrary-code sandbox, multi-region consensus, cross-host
artifact store, unknown-provider exactly-once guarantee or live definition migration is claimed.

## Reproduction

From this directory with a real ANCHOR_DATABASE_URL, use locked sync/checks and `pytest`.
`python -m pp_anchor.cli demo --output ABS_EMPTY --seed 1729` exercises recovery;
`benchmark --profile ci|standard --output ABS_EMPTY --seed 1729` writes provenance;
`clean-demo --output ABS_OWNED` removes only marked state and refuses unknown files or
symlinks. Foreground scheduler/worker/serve and backup/restore commands are documented in
OPERATIONS.md.
