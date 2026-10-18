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

Independent review also supplied an SDK instance whose customer records were
out of matrix-node order. The keyed verifier accepted it while the positional
scheduler used the wrong service/window record. The exact reproduction now fails
explicit canonical-order validation; sorting the records produces a verified
schedule. `test_noncanonical_sdk_customer_order_is_consistently_invalid` checks
both rejection and the corrected waiting/service calculation.

The accepted clean matrix at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2` passed
75 tests on each required interpreter, builds, strict checks and an actual
wheel-installed demo outside source. The seeded demo improved `(4,999)` to
`(4,657)`, rejected a duplicate and emitted JSON/maps/timelines for a new-request
plan `(4,606)`. Replanning changes the instance, so those two final objectives do
not define a comparable improvement ratio.

The corrected serial standard run at
`ec1d0106df086a48923016c33199cfbda0aebbc0` found verified plans in all 180
measured scale trials. Its 90 paired comparisons all improved travel at unchanged
fleet count; median reductions were 20.71%, 31.23% and 9.73% for 25/100/500 stops.
An earlier improvement-only run exposed an evaluation omission: those scenarios
did not demonstrate non-improvement. The corrected benchmark separately measures
a tiny baseline already at an independently enumerated optimum `(1,8)`. One
warmup and five real pairs execute 20 iterations each and produce five verified
ties. An inferior but feasible injected baseline is rejected by the control test.
Accepted CI also publishes four losses among its ten scale comparisons. These
results establish neither universal search dominance nor large-instance optimality.

The standard command took 709.636 s and process peak RSS reached 81,141,760 bytes.
Timing exposed the next practical limitation: 86 of 180 measured scale algorithm
trials exceeded their cooperative wall allowance. At 500 stops, an 8-second
allowance produced a maximum 10.839 s baseline reconstruction and 8.554 s search.
The incumbent survived, but these are not strict realtime deadlines. Bounded
regret lookahead trades completeness for runtime; profile schedule recomputation
before introducing independently tested caches or finer cancellation boundaries.

[Benchmark measurements and provenance](BENCHMARKS.md) link the accepted raw
report and outer immutable verification wrapper. Their source hashes cover
different enumerated inputs and are intentionally distinct. Large-instance gaps
remain unknown; synthetic geometry and generous capacity are not production-road
performance evidence. Reloads, transfers, traffic updates and mid-edge snapshots
remain unsupported.
