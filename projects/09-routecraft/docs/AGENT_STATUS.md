# A09 Routecraft final status

Status: complete
Phase: P6 project verification complete; final docs handed to coordinator.
Completed gates: RC-01 through RC-08. Remaining project gates: none.
Active edits: none after this docs-only handoff. No worker Git/shared-root edits.

The original integer-unit routing core includes greedy/bounded-regret insertion,
directed relocation/swap/reversal, adaptive destroy/repair and acceptance, an
immutable best incumbent, independent verification and exhaustive tiny reference.
Rolling replanning enforces actual node/time/manifests and monotone executed
history. Public SDK/CLI, strict versioned JSON, real route/timeline reports,
property/failure tests, operational docs and reproducible benchmarks are present.
No solver wrapper, external service, credentials or paid dataset is required.
Default Python is 3.14.8; 3.13.16 remains required and verified.

Accepted clean matrix source:
`b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2`.
Both Python 3.13.16 and 3.14.8 passed 75 tests, format/lint, strict mypy (21 source
files), builds, isolated installed-wheel demo/cleanup, public demo and CI benchmark.
Tests took 21.48 s and 22.13 s respectively; complete dispatcher check durations
were 41.450 s and 45.191 s. The demo improved (4,999) to (4,657), rejected a
duplicate stop, and verified new-request plan (4,606). Both CI runs published six
scale gains/four losses and five separate exact-optimal control ties.

Accepted corrected standard source:
`ec1d0106df086a48923016c33199cfbda0aebbc0`.
The serial 3.14.8 standard benchmark passed in 709.636 s: 18 scale scenarios,
90 paired gains, all 180 measured scale algorithm trials feasible; separate
control: one actual warmup, five measured ties, each algorithm 20 iterations,
independently verified exact optimum (1,8), oracle enumeration 24 plans.
Median paired travel reductions for 25/100/500 stops were 20.71%/31.23%/9.73%,
with equal fleet counts within each pair. Process peak RSS: 81,141,760 bytes.
Replanning, exact tiny checks and source stability all passed.

Actual limits: standard caps are 60 iterations plus 0.4/2/8 wall seconds; atomic
operations overran those allowances in 86 of 180 measured scale trials. The
largest observed baseline/search durations at 500 stops were 10.839/8.554 s
against 8 s. This is cooperative stopping, not strict realtime compliance.
Heuristic optimality gap remains unknown. Fixtures are synthetic with generous
capacity; window regimes do not necessarily bind every route. No cargo transfers,
reloads, traffic/matrix updates, live road routing or mid-edge states are claimed.

Evidence links and all acceptance mappings: [ACCEPTANCE](ACCEPTANCE.md).
Actual tier statistics, budgets and provenance: [BENCHMARKS](BENCHMARKS.md).
Outer immutable-source digest:
`75771d0bde227d959163d644c0ffd95ed62cfc4c4e53b4ad337ef2679bc325ee`.
Raw application digest at measurement time:
`36ababf28a3a00a087fcae837c06ef1370f30928c011e2db64d0bf03f5585685`.
Their scopes differ and must not be substituted. Lock:
`9aef9e96a988bfdd7403447241e67af694abf1c7d3910e57cae691e55643a011`.
Wrappers record clean source before/after; this final update changes only
CASE_STUDY, BENCHMARKS, ACCEPTANCE and this status document. It does not rewrite
raw evidence, claim that a report measures its own future commit, or claim remote
CI/push state, which the coordinator reports separately.

Resolved review defects: a second replan could reset already-started history;
monotone started/prefix/time checks now reject it. Noncanonical SDK customer order
could disagree between positional optimizer and keyed verifier; explicit canonical
order validation now rejects it consistently, with the review repro as regression.
The first standard attempt omitted a non-improvement control; preserved attempt
artifacts are superseded by the accepted corrected run. Historical development
records and tiny sample artifacts remain labeled with their measured dirty source.

Next administrative action: coordinator commits this final docs handoff. All code
is frozen; no reruns or implementation changes were performed for this update.
