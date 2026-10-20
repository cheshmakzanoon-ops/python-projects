# Workflow state, transactions and recovery

Anchor's durable unit is one workflow run. A serialized definition pins a DAG and a
canonical digest; an ordered history records decisions. PostgreSQL projections make
activities and timers available to workers. They are committed with their history,
never reconstructed from a process's unsaved memory after acknowledging success.

## Three responsibilities

| Component | Responsibility | Authority |
| --- | --- | --- |
| `replay/graph.py` | Compile predecessor counts, successors and reverse cleanup barriers. | The pinned definition, without I/O. |
| `replay/reducer.py` | Consume one event, validate its phase and produce stable logical commands. | Recorded events, without clocks or external calls. |
| `persistence/transition.py` | Hold one run-row lock, reconstruct once, append events and project commands atomically. | The caller's PostgreSQL transaction. |
| `persistence/engine.py` | Idempotent ingress, admission, claims, lease checks, provider adapter and read snapshots. | Constraints, row locks and database time. |
| `workers/runtime.py` | Execute handlers outside transactions and acknowledge through the lease boundary. | A bounded pool of explicitly at-least-once executions. |

`RunTransaction` owns a transient reducer state for a single database transaction.
It never caches that state across commit, rollback or pool checkout. Timer batches,
signal broadcasts and explicit compensation retries reuse it within their transaction.
A failed projection discards that entire object and every SQL write; the next operation
reconstructs from committed history.

## Forward transition

```mermaid
sequenceDiagram
    participant W as Worker
    participant E as Engine transaction
    participant R as Pure reducer
    participant D as PostgreSQL
    W->>E: finish(claim, result)
    E->>D: Lock run, then task; check epoch and database deadline
    E->>D: Read pinned definition and ordered history
    E->>R: Reconstruct state; verify committed projection
    E->>R: Consume completion
    R-->>E: Stable commands
    E->>D: Append event and project tasks/timers/status
    E->>D: Commit
    E-->>W: Acknowledged
```

The run row is always locked before task/projection mutations. Competing claimers
use `FOR UPDATE SKIP LOCKED` on run rows, then select a ready task in that run.
The task changes to `running`, its epoch/attempt increment and an attempt/history
record is created before commit. Handlers run only after that claim transaction ends.
An expired task is reclaimable with a new epoch. A stale completion or heartbeat
cannot modify it, even if the old process resumes.

On completion, the engine checks the persisted task status, epoch, deadline, attempt,
step, activity and compensation identity. The check occurs while holding the run/task
locks: no competing transition can reclaim that run before commit. PostgreSQL time,
not a worker clock, decides deadline authority. A slow handler still needs heartbeats;
this protocol is not a promise that operating-system execution stops at lease expiry.

The compiled frontier starts with zero-predecessor steps. Completing a step decrements
only its successors' unsatisfied counts; newly ready nodes are emitted in definition
order. Logical IDs remain `step:NAME`, `compensate:NAME` and `terminal:STATUS`.
Immediate joins and pre-delivered signals use a depth-first explicit stack, preserving
the history order without one Python frame per step. A long history is still replayed
once per transaction; durable replay snapshots are not implemented.

## Cancellation and reverse causality

For `allocate -> join -> publish`, cleanup must perform `unpublish` before `release`.
Emitting commands in reverse order is insufficient: two workers can claim both
commands concurrently. Anchor creates the logical cleanup tasks together but blocks
predecessor cleanup until the nearest compensable descendants have **completed**.
The graph crosses intervening joins, signals and timers when computing these barriers.

```text
Forward resource dependency:    allocate -> join -> publish
Rollback dependency:            release <- unpublish

After cancellation:             unpublish=pending, release=blocked
While unpublish runs:           unpublish=running, release=blocked
If unpublish exhausts retries:  unpublish=failed,  release=blocked
After successful repair:        unpublish=completed, release=pending
After release commits:          workflow=compensated
```

Independent rollback branches may proceed concurrently. An ancestor waits for every
required branch; a failed descendant does not prevent an unrelated cleanup from
finishing. The reducer's `pending`/`blocked` phases and the SQL scheduler projection
advance together. `retry_compensation` grants another bounded batch to failed cleanup;
it does not bypass predecessors or label failure as success.

Cancellation locks the run and atomically:

1. Records cancellation and changes the workflow to `compensating` or terminal `failed`.
2. Cancels pending/running ordinary tasks and closes their current attempt accounting.
3. Persists the synthetic provider's terminal fence.
4. Creates cleanup tasks, marking dependent cleanup `blocked` before commit.

Every **scheduled** compensable step is included, including in-flight activity and
pending work. The engine cannot know whether an unacknowledged external effect occurred.
Cleanup handlers must therefore be idempotent and tolerate an absent effect. The fence
prevents a paused synthetic publication from recreating an effect after cleanup. An
arbitrary external provider needs its own equivalent contract; row locks cannot revoke
an HTTP request or roll back another database.

## State and task phases

| Workflow state | Ordinary execution | Compensation |
| --- | --- | --- |
| `running` | Ready activities can claim; timers/signals can release successors. | None. |
| `compensating` | Ordinary tasks are cancelled; late acknowledgements are fenced. | Ready leaves can claim; ancestors remain blocked; failure is visible. |
| `completed` | All definition steps completed normally. | None. |
| `compensated` | No further ordinary work. | Every required cleanup completed. |
| `failed` | Terminal failure/cancellation with no cleanup to perform. | None. |

Task `blocked` means a cleanup dependency is unfinished; it is not a delay timer or a
failure. Task `pending` may still have a future retry deadline. Task `running` means
an active claim, not proof that the process is alive. A cancelled attempt's accounting
is closed even when its handler has not physically stopped.

## History compatibility and coherent reads

The event codec is independent of the user definition's version. New runs write event
`schema_version=2`. Their replay checks legal event kinds, exactly one initial start,
scheduled/unfinished step identity, compensation phase and terminal-state boundaries,
in addition to sequence, definition digest and command IDs. Unknown or mixed codecs
are rejected. A non-existent step cannot complete a run by merely matching its count.

Version-one histories retain their original command stream and acceptance rules.
Continuing such a run appends version-one events; it never relabels or rewrites stored
history. Current workers still apply causal cleanup eligibility to its projections.
A first claim of an older compensating run reconciles pending/blocked eligibility under
its run lock. Historical out-of-order cleanup is retained as historical behavior, not
retroactively certified safe. Do not mix old and new worker binaries during upgrade.

Read-side status and replay use a repeatable-read, read-only PostgreSQL snapshot. A
writer may commit between their run-row and history queries without producing a
false mismatch or a hybrid response. Replay verifies that the final sequence/status
matches the committed run projection and that the stored definition matches its pin.
Truncated history or inconsistent projections fail clearly; inspection does not
silently repair them or execute activities.

The definition digest pins serialized activity names and parameters, not the Python
bytecode registered under a name. Deploy a new activity identity/definition for a
changed external-effect contract. Anchor provides neither suspended-stack migration
nor arbitrary handler-code versioning.

## Persistence and failure boundary

Claims, history, timers, signals, idempotency records and the synthetic provider are
ordinary PostgreSQL tables. Durable acknowledgements assume `fsync`,
`full_page_writes` and `synchronous_commit` remain enabled. A process killed between
history append and timer projection leaves neither committed: another claim after
lease expiry reconstructs the prior history and emits the transition once.

Backup captures engine/provider state in one repeatable-read snapshot. Restore copies
into an empty schema in one transaction. Neither process-kill tests nor checksummed
archives prove every storage-controller/power-loss behavior. The reference export uses
an owned local filesystem shared by its workers; it is not a cross-host artifact store.
