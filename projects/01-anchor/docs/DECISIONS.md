# Design decisions

## Explicit DAG and replay rather than suspended execution

The definition is an immutable, topologically ordered graph. Activities perform external
work; a pure reducer consumes persisted outcomes and schedules successors. This makes
command identities and incompatible replay inspectable without serializing a Python
stack. It deliberately omits arbitrary loops, dynamic workflow code and live migration.

A successor index and unsatisfied predecessor counts drive the forward frontier. A full
scan of every step after every event was simple but made a batch do repeated unrelated
work. The compiled graph keeps deterministic definition-order emission while touching
only successors of newly completed steps. An independent transitive-ancestor model
checks both forward scheduling and reverse rollback on generated graphs.

## One transaction-local reconstruction rather than a process cache

`RunTransaction` holds the run lock and reconstructs once for the caller's transaction.
It reuses that state through timer batches, signal broadcasts and immediate internal
commands, then is discarded. This removes repeated history reads inside one atomic
transition without introducing cache invalidation across processes or failed commits.
A fault after history insertion but before timer projection rolls back both; a fresh
operation cannot inherit the failed in-memory state.

Each later transaction still replays committed history. A persistent checkpoint cache
would need a versioned integrity boundary and independent equivalence tests. It is not
introduced merely to advertise faster long-running workflows. The bounded
[transaction diagnostic](BENCHMARKS.md#scheduler-transaction-diagnostic) measures the
specific replay/read behavior that changed.

## Run-row serialization rather than scheduler leadership

Every mutation takes the run row before task rows. Independent schedulers/workers use
`SKIP LOCKED` to share runs without electing a leader. Unique ingress keys, event
sequences and logical command IDs reinforce that transaction boundary. They do not
replace it. This limits transition throughput inside one busy run and requires keeping
external work outside transactions.

Read-only status/replay instead use repeatable read. Comparing a run projection with
history under separate read-committed snapshots can incorrectly diagnose a healthy
concurrent commit as corruption. A single read snapshot avoids that false positive
without blocking writers for the duration of replay.

## Reverse causal cleanup rather than reverse insertion order

For dependent resources, enqueueing `unpublish` before `release` does not stop another
worker from leasing `release` first or while `unpublish` is paused. Cleanup eligibility
therefore follows the reverse graph, including paths through non-compensable joins,
timers and waits. Independent leaves can run concurrently; a failed leaf keeps its
ancestors blocked until an explicit retry succeeds.

The logical compensation commands are still created together with stable IDs. Pending
versus blocked is a scheduler projection, not a new business operation. This preserves
historical command identity and avoids encoding queue insertion time as an accidental
ordering guarantee. An ordinary cancellation also closes the current attempt records;
leaving them `running` would falsely report live work after terminal cleanup.

## Provider idempotency and fencing rather than universal exactly-once

A worker can die after an external commit but before acknowledging the engine. Retrying
is unavoidable. The downstream operation must keep the same business key across retries.
The synthetic provider persists publication count and an irreversible cancellation
fence; another provider must supply its own equivalent behavior.

Include a logical operation identity when a run performs several effects. For custom
activities, `f"{context.business_key}/{context.task.step}"` distinguishes steps while
remaining stable across attempts and matching their compensations. Do not append the
attempt number or lease epoch to a business idempotency key. The built-in synthetic
publication uses one effect per run; it is not a general multi-effect provider service.

## Event codec versions rather than silent reinterpretation

Version two validates state-machine transitions as well as emitted command IDs.
Version-one histories continue under their original codec and remain inspectable without
rewriting evidence. New scheduler projections enforce causal rollback for current workers
on either codec. Unknown/mixed event versions and committed projection/history mismatches
fail closed. The codec version, definition version and snapshot archive format are distinct.

An upgrade must stop old writers, take a coherent backup and validate restored/replayed
state before restarting. Old binaries do not understand version-two events or blocked
cleanup tasks; binary rollback requires the corresponding pre-upgrade backup, not a
mixture of interpretations over current data.

## Trusted local control plane

The HTTP adapter assumes trusted loopback clients and has no authentication. Bounded
bodies, strict request contracts and owned cleanup protect development workflows, not a
public multi-tenant deployment. Database schemas separate owned runs, not hostile users.
Authentication, deployment policy, cross-region consensus and a code sandbox require
separate designs.
