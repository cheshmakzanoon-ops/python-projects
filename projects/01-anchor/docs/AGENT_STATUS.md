# Anchor status: locally verified; immutable portfolio verification pending

Implementation source is stable and paused for coordinator integration. No Git mutation
has been performed by this worker. All AN-01–AN-08 local scenarios pass; coordinator
review, final committed-source evidence and full standard benchmark remain required.

## Actual verification

- CPython 3.13.16: **54 passed**, 81.39 s, real PostgreSQL and real child-process faults.
- CPython 3.14.8: **54 passed**, 67.15 s, same required suite.
- Locked Ruff format/check, strict mypy: exit 0.
- `uv build`: sdist and wheel built, exit 0.
- Clean `/tmp/anchor-wheel-install` installed the wheel plus exact exported locked runtime
  dependencies. Outside the checkout: import path verified, schema.sql resource present,
  public definition SDK and module CLI help passed.
- Defined own core: **96% combined line/branch coverage**, 216 branches, 14 missing
  branches (93.5% branch). Scope: definitions, reducer/replay, PostgreSQL adapter/snapshot,
  scheduler and worker. Coverage includes real persistence/fault paths, not transport wrappers.
- Real export CLI acceptance creates deterministic 60-row CSV/ZIP, kills the publishing
  worker after provider commit, retries epoch two, verifies one publication/replay, and
  cleans only its owned schema/output. The test independently reconstructs every CSV row.

Evidence: `artifacts/development-verification.json` captures source/lock/root hashes and
actual outcomes; this capture was taken after checks with implementation writes paused.
The coordinator must still perform pre/post capture on an immutable committed tree.
`artifacts/development-demo-*` and `development-baseline-ci.json` are authentic earlier
captures, explicitly labelled historical development evidence.

## Implemented contracts and acceptance

AN-01 deterministic replay/command diagnostics; AN-02 submission SIGKILL before/after
commit plus concurrent canonical idempotency; AN-03 SIGKILL after provider effect before
ack; AN-04 epochs/expired heartbeat plus resumed real stale process; AN-05 persisted timers
on restart with two schedulers and injected timer clock; AN-06 every join order, early and
duplicate signals, cancellation/completion races and resumed pre-effect worker fencing;
AN-07 exhausted failed cleanup remains unresolved until explicit successful retry; AN-08
two schedulers/adapters and six worker slots account for all flaky accepted runs with no
orphan task. See ACCEPTANCE.md and corresponding test names.

Additional controls: finite/bounded definition/payload/result validation; bounded admission
with HTTP429; body size bounds including chunked input; paginated history; snapshot
repeatable-read backup/checksummed bounded archive/atomic empty-target restore; path and
symlink safeguards; provider payload conflict detection; preserved asyncio cancellation.

## Remaining required verification

1. Coordinator independent review and immutable committed-source checks, including IN-01.
2. Standard benchmark: full 5,000 workflows × five activities, two schedulers; runner uses
   one measured repetition plus bounded warmup because five full runs are costly. This
   exception is explicit in report parameters and BENCHMARKS.md; ci retains five measures.
3. Rerun final ci benchmark against immutable source (first baseline predates final indexes).
4. Root metadata should record both required interpreters. Current default remains 3.13.16
   for integration stability; 3.14.8 full suite passed and is eligible for default promotion.

No essential external blocker is known. The coordinator supplies the database URL securely
through ANCHOR_DATABASE_URL; no credential values are saved. Linux is required for SIGKILL
process tests. No arbitrary-code sandbox, multi-region consensus, cross-host artifact store,
unknown-provider exactly-once guarantee or live workflow-definition migration is claimed.

## Reproduction and next action

From this directory with a real ANCHOR_DATABASE_URL, run locked sync/checks and `pytest`.
`python -m pp_anchor.cli demo --output ABS_EMPTY --seed 1729` exercises recovery.
`benchmark --profile ci|standard --output ABS_EMPTY --seed 1729` writes provenance.
`clean-demo --output ABS_OWNED` refuses unknown files/symlinks/non-demo schemas.
Foreground scheduler/worker/serve commands are in OPERATIONS.md. Background benchmark
processes are not running. Next action: coordinator integration/immutable verification;
worker stays available for concrete review defects without changing source meanwhile.
