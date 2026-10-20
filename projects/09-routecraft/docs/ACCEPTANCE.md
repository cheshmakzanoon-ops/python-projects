# Acceptance and evidence mapping

Historical clean-source verification covers all eight Routecraft gates. Source commit
`b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2` passed format, lint, strict mypy,
**75 tests on each of Python 3.13.16 and 3.14.8**, sdist/wheel builds, an isolated
wheel-installed demo/cleanup, the public demo and CI benchmark. The accepted
corrected standard run passed at `ec1d0106df086a48923016c33199cfbda0aebbc0`.
All three outer wrappers identify the same Routecraft code/test/lock source digest.

| Gate | Independent evidence |
| --- | --- |
| RC-01 | `test_reference_objective_and_truthful_unknown`, `test_rc01_six_customer_complete_enumeration`; directed optimum 8, uniform six-customer optimum 7 and exactly 5040 labeled enumerations; generated directed matrices compare feasibility and objective bounds against complete enumeration |
| RC-02 | `test_verifier.py` rejects missing/duplicate/unknown stops, capacity, window, service/return shift and cache corruption; the independent-review SDK tuple-order regression now returns explicit invalid input rather than a scheduler/verifier disagreement |
| RC-03 | Forward cost 8 versus reverse cost 30, arrivals 6/14/23; hand calculations test the optimizer and independent checker; randomized directed moves are verified separately |
| RC-04 | Injected invalid moves, cancellation, cancellation after progress and zero wall deadline retain the immutable verified incumbent; cooperative deadline overrun limits are disclosed in BENCHMARKS |
| RC-05 | Identical input/seed/iteration budgets reproduce plans, trajectories, operator counts and actual 80 iterations; retained-best trajectory is monotone |
| RC-06 | Accepted standard: 18 scale cases, 90 paired gains, 180 feasible algorithm trials; separate exact-optimal control records five actual ties after one warmup; both CI matrix runs retain six gains/four losses; valid-but-suboptimal control injection is rejected |
| RC-07 | Delayed actual boundary and added request succeed; transfer, invented cargo, manifest, frozen-prefix/definition, matrix and mid-edge failures are rejected; repeated replanning cannot reset started status, shorten history or move time backward |
| RC-08 | Strict JSON roundtrip, subprocess public CLI and isolated installed wheel; independently verified JSON and actual SVG route/timeline reports; heuristic unknown remains distinct from exhaustive infeasibility; stale success outputs and unverified publication are rejected |

`tests/property/test_oracle.py` explores generated directed matrices, capacity
infeasibility and island schedules. The oracle uses no production neighborhood
or scheduling code. It shares the independent verifier, while hand-derived costs
and formula bounds provide an additional independent check.

Accepted immutable evidence:

- [Python 3.13.16 wrapper](../../../docs/evidence/final/python313/routecraft-3.13.16.json)
  and [75-test/build/wheel log](../../../docs/evidence/final/python313/routecraft-3.13.16-check.log).
- [Python 3.14.8 wrapper](../../../docs/evidence/final/python314/routecraft-3.14.8.json)
  and [75-test/build/wheel log](../../../docs/evidence/final/python314/routecraft-3.14.8-check.log).
- [Corrected standard wrapper](../../../docs/evidence/final/standard/routecraft-3.14.8.json)
  and [actual standard measurements](../../../docs/evidence/final/standard/routecraft-3.14.8-benchmark-benchmark.json).

Read the wrappers' enumerated source scopes separately from the application raw
hashes; their input sets differ. Historical dirty development samples remain
labeled as such and do not replace this evidence. Numerical results, observed
atomic wall overruns and unsupported scenarios are in [BENCHMARKS](BENCHMARKS.md).

## Boundary and reporting regressions

`tests/unit/test_stop_boundaries.py` verifies one-shot cancellation, deadline/cancellation between construction attempts, and incumbent retention. `tests/integration/test_boundary_safety.py` rejects symlink ancestors, unknown/duplicate JSON fields, unsupported versions, invalid matrix-version identities, and successful CLI exit codes for invalid solver inputs. `tests/integration/test_timeline_intervals.py` checks that drawn travel durations equal the verified travel objective and that zero-duration service is not stretched. Current test counts and interpreter checks are recorded in [verification](VERIFICATION.md).
