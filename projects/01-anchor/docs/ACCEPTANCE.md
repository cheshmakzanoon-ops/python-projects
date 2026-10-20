# Acceptance mapping

| Gate | Test / evidence |
|---|---|
| AN-01 | `test_AN01_AN06_all_join_orders`, generated DAG oracle, replay of every integration/demo run; incompatible digest identifies event 1 and changed commands event 2 |
| AN-02 | `test_AN02_process_crashes_and_ingress`: real SIGKILL before/after commit, concurrent duplicates, canonical conflict and one task/run |
| AN-03 | `test_AN03_kill_after_effect_before_ack`: real child process killed after provider commit, expired attempt, epoch-two completion, one publication |
| AN-04 | `test_AN04_epoch_and_expired_heartbeat`: expired lease, takeover, stale heartbeat/result/failure rejected |
| AN-05 | `test_AN05_persisted_timers_restart_two_schedulers`: new Engine connection, clock injection, competing scheduler ticks, one firing per persisted timer |
| AN-06 | early duplicate/conflicting signals; completion/cancel races; paused-before-effect fencing; every parallel join order |
| AN-07 | `test_AN07_cleanup_failure_unresolved_until_actual_success`: bounded ordinary and cleanup retries, failed cleanup remains compensating, explicit recovery succeeds |
| AN-08 | `test_AN08_two_schedulers_workers_faults_accounting`: two adapters/schedulers, six worker slots, seeded transient failures, every accepted run completed, zero orphan tasks |

`pytest` uses actual PostgreSQL for all persistence tests, importlib mode and installed
src-layout package. `ANCHOR_DATABASE_URL` is mandatory; there are no required-service
skips. A simple independent readiness set model and every permutation of a three-way
join check reducer behavior. The CLI demo writes actual history, ZIP and timeline.

Final check commands: `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`,
`uv build`, and a clean outside-tree wheel-install smoke test, all through the locked
project environment. Source evidence from development is labelled dirty and cannot
substitute for immutable committed-tree verification.

The initial immutable acceptance snapshot passed 54 tests on both 3.13.16 and 3.14.8. Real paused-process tests
in `test_process_fencing.py` extend AN-04/AN-06 across an actual child process boundary.
The installed CLI test independently reads every exported row and resets owned state.
The snapshot test backs up/restores real PostgreSQL rows and resumes a persisted timer.
Defined core branch coverage is 93.5% (216 branches, 14 missing), combined coverage 96%.
See `../artifacts/development-verification.json` for actual commands and source scope.
Later changes and their validation are recorded in [VERIFICATION.md](VERIFICATION.md).

## Core transition invariants

`tests/integration/test_causal_rollback.py` extends the acceptance scenarios with an
actual PostgreSQL parent/child resource foreign key, paused concurrent cleanup, forked
rollback failure/retry, codec-one continuation, closed cancellation attempts, coherent
read snapshots and process death between history and timer projection. The four initial
regressions were observed failing before the core refactor: cleanup overtaking, repeated
batch history reads, ignored event codecs and unrelated-step completion.

`tests/property/test_rollback_model.py` independently derives transitive ancestors on
generated DAGs. It checks the forward frontier and reverse cleanup frontier, injects
one cleanup failure/retry, and verifies full replay. `tests/unit/test_replay_invariants.py`
checks illegal phase transitions, mixed codecs and historical command compatibility.
These checks supplement the original acceptance evidence; they do not relabel it.
