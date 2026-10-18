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

Required tests are real and have no skip/xfail paths. Property examples combine values, negative/out-of-order times, streams and keys; admission properties generate identical and conflicting offset retries. The oracle deliberately enumerates batch window boundaries and matches accepted retained pairs separately from runtime window assignment/heaps.

Coverage scope includes model, event_time, operators, runtime, ingress, sinks and sources, including persistence branches. CLI plumbing, workload generation and the independent oracle are excluded from this core metric; CLI behavior is exercised through subprocess acceptance tests. See AGENT_STATUS for exact measured results and immutable coordinator evidence when available.
