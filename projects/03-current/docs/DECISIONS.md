# Decisions and persisted contracts

| Decision | Reason and consequence |
| --- | --- |
| One admission ordinal for events and controls | Offsets alone cannot reconstruct whether idleness preceded an old event. Sorting by event time would change the recorded late policy. Retain ingress for replay. |
| Fixed input topology, one ordered state owner | Coherent global controls and barriers are easier to reason about than parallel mutable aggregates. Keyed preparation does not promise aggregate CPU scaling or distributed ownership. |
| Explicit idle, resume and end | Idle inputs can return; ended inputs cannot. All unfinished inputs idle freezes progress, while all inputs ended finalizes it. No processing-time heuristic changes event-time history. |
| Global timestamp-based late acceptance | Every operator receives the same accepted set. Exact boundary `t + lateness == watermark` is accepted; operator expiration is strict. |
| Half-open windows, inclusive joins | Window boundaries assign readings unambiguously; pair identity uses exact admission ordinals. Integer floor division supports negative times. |
| Canonical join state plus derived bucket index | Checkpoint meaning remains simple, while opposite-stream time buckets avoid quadratic same-stream scans. Lazy ordered merging preserves delivery order and staging backpressure. |
| SQLite FULL-synchronous WAL | SQLite handles byte durability and atomic prefix/state/result/outbox publication; the event-time algorithms remain application code. Process-exit tests establish crash behavior, not dishonest storage or universal power-loss safety. |
| Connection lock plus optimistic checkpoint fence | A connection cannot mix acknowledgements with an in-flight transaction. A second stale connection cannot overwrite another committed state. This rejects stale work rather than electing an owner. |
| Settle submitted I/O before returning cancellation | Executor threads survive task cancellation. Waiting prevents a caller from closing/recovering a connection while publication is still committing. Cancellation latency can include the database operation. |
| Immutable delivery identities, greatest revision view | `(job_id, operator_id, logical_result_key, revision)` detects conflicting retries. Independent sink commit precedes acknowledgement; delayed old revisions are harmless. |
| Logical resource reservation before mutation | Counts provide explicit predictable backpressure without claiming byte-precise memory quotas. Failure requires fresh recovery; only the state budget may change on checkpoint restore. |

## Version compatibility

Wire and SQLite schema formats remain version one. Checkpoint code version is `current-3`. It embeds complete Config, job, processing position, watermarks/idleness, windows/revisions, retained joins, disposition counts and diagnostics. Restore rejects inconsistent persisted state and incompatible semantic configuration. `state_limit` is an operational resource setting and may change if retained state fits; changing windows, lateness, interval, input order/topology, worker count or pipeline version requires a fresh job/rebuild.

`current-1` and `current-2` checkpoints require a controlled rebuild from unchanged retained ingress. Version three fixes premature terminal progress when one input ends while another is idle. Earlier checkpoints may already have rejected resumed events or expired correction state. Even a checkpoint that now shows all inputs ended cannot prove its prior history was correct, so selective acceptance is unsafe. Editing the version string cannot reconstruct missing revisions.

The [runbook](OPERATIONS.md) gives executable raw-ingress/config extraction and configuration-preserving identity-pipeline replay commands. A new job namespace prevents corrected revisions from conflicting with old external immutable deliveries; reconciliation is an operator decision. Custom mapper/predicate deployments retain their original code and pipeline version and use the Python API. No automatic checkpoint migration or pickle deserialization is provided.

## Deliberate limits

Current does not compact immutable identity history, dynamically rescale topology, coordinate distributed ownership or provide arbitrary-external-effect exactly once. It also does not bound batch result export/reference reconciliation memory. Those changes need separate designs and evidence; queue/state counts do not establish total process capacity. See [architecture](ARCHITECTURE.md) for invariants and [benchmarks](BENCHMARKS.md) for measured scope.
