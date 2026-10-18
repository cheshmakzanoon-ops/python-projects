# Case study: cancellation after an unacknowledged effect

The product coordinates a synthetic export across crashes. A worker can die between
provider publication and engine acknowledgement. Retrying is unavoidable, so activities
are explicitly at least once and the provider persists a stable business identity.

The original reducer and PostgreSQL adapter own scheduling, replay, run-first lock order,
epoch leases, retries and compensation. Frameworks provide transport, validation and the
SQL driver. A durable explicit DAG was chosen over serializing suspended Python stacks.

The most consequential design hazard was cleanup based only on completed activities:
an in-flight publication can be paused before its effect, cancellation cleans up,
and the old worker then resumes. Epoch checks at completion cannot undo that external
publication. The regression reproduces this order directly: claim publication, cancel,
complete cleanup, resume provider call and completion. Provider call must raise
`ProviderFencedError`; completion must raise `StaleLeaseError`, with zero publications.

The fix includes scheduled in-flight steps in compensation and commits a terminal
provider fence alongside cancellation. Cleanup failure is still recorded as unresolved:
a fence prevents resurrection but does not manufacture cleanup success. A later failed
cleanup test exhausts retries, inspects `compensating`, repairs the handler, admits a
new bounded batch, and only then records `compensated`.

A second process test actually SIGKILLs a worker after provider commit. Replay shows an
expired first attempt, a higher lease epoch, and successful completion with one logical
provider publication. This demonstrates the specific idempotency/fencing contract of
this provider; arbitrary external providers need their own equivalent enforcement.

Actual measurements are linked from BENCHMARKS.md when completed. Process-kill tests
cannot establish behavior under every power-loss/controller failure. Long histories
currently replay on each transition and are the clearest next performance boundary;
versioned integrity-checked snapshots would be justified after measuring that workload.

The initial measured ci baseline completed five 100-workflow/500-activity runs at median
3.95 workflows/s under substantial shared-host contention. The isolated 100,000 future
timer probe fired none, took 0.059 seconds for an idle tick, and added 0 KiB peak RSS.
Those historical results include exact source hashes in artifacts; they predate final
queue indexes and must not be presented as a controlled speedup comparison. Final local
correctness is 54 passing tests on both interpreters with 93.5% branch coverage of the
defined core. The case study's next justified optimization remains long-history snapshotting,
after profiling an appropriate workload rather than chasing a synthetic throughput target.

## Committed standard measurement

The [full standard report](../../../docs/evidence/final/standard/anchor-3.14.8-benchmark-benchmark.json) records source `59443e2`: one measured 5,000-workflow run after bounded warmup, with 25,000 successful activities and 250 injected retries. All completed in 233.23 seconds including admission, or 21.44 workflows/s, with no orphan tasks. This burst intentionally queues all workflows before execution: created-to-start p95 was 189.68 seconds, so the throughput is not a low-latency service guarantee. The separate 100,000-future-timer probe fired none and took 24.15 ms for an idle tick. The one-full-run costly-workload exception and Linux resource context are retained with the evidence; historical development values above are not a controlled before/after comparison.
