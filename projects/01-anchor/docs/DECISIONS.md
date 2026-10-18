# Decisions

1. **Explicit DAG rather than suspended Python coroutines.** A small auditable reducer
   gives stable command IDs and deterministic replay. It omits arbitrary loops and
   workflow stack capture; external work always runs as activities.
2. **Run-row serialization rather than distributed scheduler leadership.** Independent
   schedulers claim rows with SKIP LOCKED and all transitions use the same run-first
   lock order. This avoids a leader election service and makes command/history atomicity
   reviewable. It limits transition throughput within one very busy run.
3. **Reconstruct short histories rather than trusting an in-memory cache.** Every
   mutation replays persisted events. This makes restart semantics simple and catches
   divergence immediately, at the cost of quadratic work for extremely long histories.
   Snapshotting would require a versioned integrity-checked replay boundary and is not
   implemented speculatively.
4. **At-least-once execution plus provider idempotency.** A process can die after an
   external effect and before the database acknowledgement. No local transaction can
   make a remote provider exactly once. The demo provider persists its own stable
   business key, publication count and irreversible cleanup fence.
5. **Cancellation fences include in-flight steps.** Compensating only completed steps
   is incorrect: a worker can have acted without acknowledging. Every scheduled step
   with a cleanup is considered, including leased steps. A provider fence precedes
   cleanup success, and failed cleanup remains unresolved.
6. **Database clock authority.** Local process clock skew cannot renew expired leases.
   Timer testing injects offset only in timer eligibility; production leases always
   compare database time. Retries record exact selected delay in history.
7. **No remote authentication story implied.** The control plane is a trusted loopback
   development API, with request validation and bounded bodies. Deployment auth,
   multi-region consensus, arbitrary-code sandboxing and live definition migration are
   explicitly outside this product's contract.
