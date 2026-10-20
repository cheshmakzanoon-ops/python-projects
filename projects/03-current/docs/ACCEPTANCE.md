# Acceptance evidence map

| Gate | Executable evidence | Invariant |
|---|---|---|
| CU-01 | `tests/property/test_oracle.py`, `tests/property/test_admission.py`, CLI demo | Independent first-committed-admission model and raw-trace batch oracle compare dispositions and finalized windows/joins; neither imports runtime algorithms |
| CU-02 | `tests/unit/test_semantics.py`, generated trace property | Negative timestamps, empty keys, half-open exact windows, inclusive joins, repeated times and multiple pairs |
| CU-03 | `test_boundaries_revisions_and_no_resurrection` | Exact lateness boundary accepted, rejected older input, late revision increments and expiration prevents recreation |
| CU-04 | `test_idle_resume_and_regressions`, demo | Stalled input holds minimum; explicit idleness advances progress; resumed old data rejected without regression |
| CU-05 | `test_process_kill_checkpoint_prefix` four parameter cases; demo | Actual child exits before stage, during transaction, before publication and after commit; only old or complete new prefix restored |
| CU-06 | `test_sink_lost_ack_out_of_order_and_conflicting_revision` | Lost postcommit acknowledgement replay, newer then older retry, conflicting immutable delivery payload rejection |
| CU-07 | `test_bounded_async_hot_key_and_writer_stall`, `test_ndjson_and_real_disk_budget`, CLI hot benchmark | Finite queues and responsive heartbeat during writer stall; 50%-hot keys; explicit outbox/admission/state limits and real SQLite page exhaustion |
| CU-08 | `test_admission_lost_ack_conflicts_and_offset_identity`, `test_map_filter_and_replay_no_double_application`, `test_restore_compatibility_and_stable_partition` | Source-offset replay is distinct from event ID reuse; no double apply; incompatible code/config fails closed |

## Core semantic and concurrency review

| Evidence | What it establishes |
| --- | --- |
| `tests/reference_trace.py`, `tests/property/test_online_trace.py` | A full-history model independently scans accepted pairs and recomputes window revisions; every generated prefix compares disposition, watermark and exact ordered delivery identity/payload, with restore every seventh record. It uses a separate finished-input set rather than production progress/index helpers. |
| `tests/unit/test_terminal_progress.py` | Ending the last active input does not finalize an unfinished idle input. Resume accepts the lateness boundary and produces the correct sum/revision. Premature terminal checkpoint state is rejected. |
| `tests/integration/test_owner_failures.py` | Same/different-job stale owners cannot replace committed state; a shared-connection acknowledgement cannot leak into a rolled-back publication; cancellation waits for the DB worker; multiple mapper failures, callback cancellation and cancelled failed I/O do not leak/hang; staged fanout stops after at most budget+1 candidates and requires fresh recovery. |
| `tests/integration/test_publication_schedule.py` | Eight failure schedules combine four publication boundaries with empty/nonempty prior prefixes, actual close/reopen and an independent control-history model. Every immutable revision and local latest row agrees with the committed prefix. |
| `tests/integration/test_delivery_restart.py` | Both sink insertion phases roll back atomically. Two jobs share logical keys safely. A real child exits after sink commit before journal acknowledgement, followed by restart, duplicate delivery and reversed revision order. |
| `tests/integration/test_state_backpressure.py` | Sliding fanout reserves state before allocation; higher state budgets recover/replay; a lower budget depends on current retained state rather than historical peak. Semantic Config changes still fail. |
| `tests/integration/test_wire_boundaries.py` | A valid 16 KiB wire record round-trips with its delimiter and retains capacity when the durable ordinal gains digits; overlimit records remain rejected. |
| `tests/unit/test_join_index.py` | Sparse probes, zero/positive intervals, negative times, inclusive boundaries, deterministic delivery order, index restore and expiration agree with a direct pair model. |
| `tests/acceptance/test_checkpoint_rebuild.py` | Real CLI exports older retained ingress/config read-only, replays under a fresh namespace with corrected late revision, preserves source bytes, rejects custom transformations and batches 2,001 input records as 1,000/1,000/1. |

The core pass adds 36 cases to the 123-case persistence review. The final count and complete interpreter/build checks are in [verification](VERIFICATION.md). The repeatable [focused join comparison](BENCHMARKS.md#focused-join-comparison) measures the changed candidate lookup against an immutable baseline; it does not substitute for the historical standard workload.

Required tests are real and have no skip/xfail paths. Property examples combine values, negative/out-of-order times, streams and keys; admission properties generate identical and conflicting offset retries. The oracle deliberately enumerates batch window boundaries and matches accepted retained pairs separately from runtime window assignment/heaps.

Coverage scope includes model, event_time, operators, runtime, ingress, sinks and sources, including persistence branches. CLI plumbing, workload generation and the independent oracle are excluded from this core metric; CLI behavior is exercised through subprocess acceptance tests. See [verification](VERIFICATION.md) for measured results and historical immutable evidence.

Accepted committed-source verification is now available: [Python 3.13.16](../../../docs/evidence/final/python313/current-3.13.16.json) and [Python 3.14.8](../../../docs/evidence/final/python314/current-3.14.8.json) each pass 32 tests, full quality/build/install checks, demo and CI benchmark at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2`. Their recorded project digest agrees with the accepted [standard execution](../../../docs/evidence/final/standard/current-3.14.8.json) at `ec1d0106df086a48923016c33199cfbda0aebbc0` under the wrapper's explicit source-input scope.

CU-01 and CU-07 also have full-workload evidence in the [raw standard report](../../../docs/evidence/final/standard/current-3.14.8-benchmark-benchmark.json): one million ordinary and one million 50%-hot-key events, each with 1,004,006 journal records including controls, complete disposition accounting, and full independent window/join reconciliation. Runtime buffer peaks are 53/95 records and retained state peaks 4,584/2,905 entries. Observed SQLite main/WAL totals are 1,679,376,416 / 2,739,242,104 bytes. This resource evidence includes a 12,177,899,520-byte process RSS high-water mark for the full trace/export/oracle/native-SQLite benchmark path; it is not an isolated-engine memory measurement.

`tests/unit/test_benchmark_memory.py` adds two CI/standard regression cases that raise a mocked RSS peak in the hot workload and require sampling after hot execution and cleanup. Earlier pre-hot samples are superseded. [BENCHMARKS.md](BENCHMARKS.md) explains throughput exclusions, the single-repetition standard run-cost exception, final-checkpoint restore scope and event-time lag semantics. Those historical records describe their stated source revisions; current validation is recorded separately in [verification](VERIFICATION.md).

## Journal and recovery integrity

`tests/integration/test_journal_integrity.py` verifies database identity before initialization, rejects unsupported schemas and triggers, and preserves existing data on rejection. It also checks bounded page limits, actual SQLite page-size accounting, checkpoint/ingress prefix consistency, and validation of persisted control and operator state. The independent-oracle property test restores after every generated processing prefix, then continues to the same expected dispositions and outputs.
