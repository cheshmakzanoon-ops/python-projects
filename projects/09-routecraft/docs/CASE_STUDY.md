# A manifest is more than capacity

The problem is to improve directed delivery schedules while preserving the fleet's
actual physical state after work has started. Time windows, return shifts and
cargo are hard constraints. Libraries render charts and run checks; insertion,
search, enumeration, manifest enforcement and verification are authored here.

A scalar capacity model was rejected for rolling planning: an empty seat on a
truck does not mean it carries a parcel. The baseline instead records IDs and
quantities of loaded jobs. New deliveries go to an unstarted vehicle; transfers
and reloads require a separate model.

A subtle implementation hazard appears during destroy/repair. Removing some
jobs from a partial started route must not remove their cargo. The vehicle still
carries every outstanding manifest job until repaired or delivered. The scheduler
therefore starts suffix delivery simulation at the full actual onboard quantity,
not the demand sum of jobs temporarily present in the partial route. Historical
prefix load includes delivered jobs plus actual onboard quantity. Every complete
candidate then passes an independently authored verifier.

`test_transfer_loaded_job_and_new_unloaded_assignment_rejected` reconstructs an
illegal route that adds the new request to the started truck and another that
moves a loaded job to an idle vehicle. Both are rejected. The positive delayed
boundary test checks that actual departure time controls the next arrival and
that the new job is handled by another vehicle. These are concrete cargo and time
regressions, not only malformed-input checks.

A review found a repeated-replan hole: resetting a previously started truck to
unstarted could erase its already frozen prefix. `test_repeated_replanning_cannot_reset_started_or_executed_history`
now reproduces the reset, shrinking-prefix and backward-time cases; monotone
state validation rejects all three before scheduling.

A second numerical trap is directed route reversal. The tiny route 0->1->2->3->0
costs 8, while its reversal costs 30, with arrivals 6,14,23. Reusing a symmetric
2-opt boundary delta would conceal 22 travel units and a shift violation. The
optimizer fully reschedules and the independent test asserts the hand result.

The seeded 25-stop demo retained a feasible incumbent, recorded rejection of a
duplicated route, and produced actual JSON/maps/timelines for the new request.
Large-scale optimality remains unknown. Cooperative deadlines can overrun one
operation; bounded eight-job regret lookahead trades completeness for runtime.
The next justified optimization is profiling schedule recomputation, then caching
only under an unchanged independent-verifier contract. Benchmark measurements
and their source identities are linked through the repository evidence index.
