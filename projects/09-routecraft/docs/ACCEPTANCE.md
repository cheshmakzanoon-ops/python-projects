# Acceptance and evidence mapping

| Gate | Independent evidence |
| --- | --- |
| RC-01 | `test_reference_objective_and_truthful_unknown`, `test_rc01_six_customer_complete_enumeration`; known directed optimum 8, uniform 6-customer optimum 7 and exactly 5040 labeled enumerations; generated matrices compare feasibility and lower objective bound against complete enumeration |
| RC-02 | `test_verifier.py` rejects missing/duplicate/unknown stops, capacity, window, service/return shift, cache objective/return/schedule corruption and malformed instances |
| RC-03 | Forward tour has cost 8; reverse costs 30 with arrivals 6,14,23; `test_directed_route_recalculation` checks the optimizer and hand result; random directed move outputs separately verified |
| RC-04 | `test_cancel_timeout_rejected_moves_keep_incumbent`, `test_cancel_after_progress`; injected duplicate operator result rejected, original immutable incumbent retained through cancellation and zero wall deadline |
| RC-05 | `test_same_seed_iteration_result_repeats` checks exact plans, trajectories, operator counts and 80 actual iterations; monotone best trajectory |
| RC-06 | `test_rc06_equal_budget_ci_publishes_every_trial` uses real seeded runs, 5 paired measurements and identical caps; benchmark publishes gain/tie/loss/unavailable, feasibility, time, efforts, trajectory, verifier latency, peak memory |
| RC-07 | `test_replanning.py` tests delayed actual boundary, successful added request, no invented cargo, transfer/manifests/prefix/definition/matrix/mid-edge failures; demo drives public replanning CLI |
| RC-08 | JSON parser round-trip, actual subprocess CLI from outside source, independent verify, SVG map/timeline assertions; timeout unknown distinguished from exhaustive infeasibility |

`tests/property/test_oracle.py` explores generated directed matrices, capacity
infeasibility and valid island schedules. The solver and oracle share the
independent verifier, not production route evaluation or neighborhood code.
Known costs and independent formula bounds prevent circular expected answers.

Local development verification and exact results are in `AGENT_STATUS.md`.
Final immutable-commit evidence is coordinator-owned and must be read with its
recorded source digest; local dirty runs are not a substitute for that release
verification. Standard benchmark evidence is pending the serial coordinator run.
