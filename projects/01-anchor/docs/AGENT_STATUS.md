# Anchor status: required local gates complete

AN-01–AN-08, immutable compatibility checks, installed-wheel demonstrations, ci profiles,
the full standard workload, and the settlement integration have passed. The default is
CPython **3.14.8**, with **3.13.16** also required and verified. Implementation remains
paused; only the coordinator changes Git and reports repository synchronization or hosted CI.

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

No Anchor local acceptance or standard-workload gate remains open. Repository-wide final
handoff and hosted CI status are coordinator-owned facts. Linux is required for SIGKILL
process tests, and the PostgreSQL URL is supplied through ANCHOR_DATABASE_URL without
saving credential values. No arbitrary-code sandbox, multi-region consensus, cross-host
artifact store, unknown-provider exactly-once guarantee or live definition migration is claimed.

## Reproduction

From this directory with a real ANCHOR_DATABASE_URL, use locked sync/checks and `pytest`.
`python -m pp_anchor.cli demo --output ABS_EMPTY --seed 1729` exercises recovery;
`benchmark --profile ci|standard --output ABS_EMPTY --seed 1729` writes provenance;
`clean-demo --output ABS_OWNED` removes only marked state and refuses unknown files or
symlinks. Foreground scheduler/worker/serve and backup/restore commands are documented in
OPERATIONS.md. Implementation and benchmark processes are stopped; writes are paused.
