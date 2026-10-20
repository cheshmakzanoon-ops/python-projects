# Design decisions

* Independent verification duplicates scheduling logic instead of sharing a
  feasibility helper. A common helper would allow the same bug to make a route
  and its check agree. Hand-calculated asymmetric costs and exhaustive enumeration
  supply additional independent evidence.
* Lexicographic `(used vehicles, directed travel)` keeps fleet count explicit.
  No scalar penalty can promote a hard-constraint violation to feasibility.
* Insertion uses immutable forward-departure/backward-latest profiles. Checking
  one inserted stop does not change the existing suffix order, so exact directed
  arc replacement and one latest-arrival comparison suffice. Profiles are owned
  by one repair call and replaced after its selected insertion; no cross-search
  invalidation protocol is needed. Full scheduling remains the fallback for an
  infeasible partial route and the implementation for reversal/block moves.
  Symmetric two-opt deltas would miss reversed internal arcs and are not used.
* Partial-route feasibility is not monotone for nonmetric matrices. A frozen
  prefix's direct depot return may be slower than a return through a remaining
  onboard delivery. Rejecting the prefix before considering insertions loses a
  valid rolling continuation. Infeasible partial routes therefore use direct
  candidate scheduling rather than an invalid cached certificate. This does not
  make greedy/regret construction complete for arbitrary matrices.
* Best and accepted-current plans are different immutable objects. Simulated
  annealing may explore worse schedules without losing the best verified answer.
  Operator weights use deterministic RNG consumption and stable tie breaking.
* Wall deadlines are cooperative at complete operator boundaries. Construction
  and repair are atomic; they may overrun the requested wall limit by one
  operation. Cancellation retains the incumbent. Once observed, cancellation is
  latched; a changing callback cannot resume work in that run. Stop conditions
  are checked between constructors/search operations and after the final operation,
  including construction with no improvement iterations. The comparison baseline
  reports a deadline crossed by its final construction too. There is no unsafe
  thread kill or claim that cancellation rolls back an already completed move.
* Exact enumeration is intentionally tiny and independent. Feasibility uses a
  path-prefix waiting-deficit formula; delegating every check to the verifier
  would let a verifier defect certify the same wrong optimum. A third test model
  enumerates labeled assignments before route permutations. None establishes
  global optimality for a 500-stop heuristic result.
* Vehicle manifests name jobs, not merely spare capacity. A started truck with
  spare capacity still cannot deliver an unloaded new job. Replanning is limited
  to named service-complete/departure nodes; interpolation through an edge would
  require a different travel-state model.
* Baselines receive the same iteration and wall-clock caps, but their work unit
  is a complete seeded greedy reconstruction, while a search iteration is a
  neighborhood. Actual counts and durations are published. Equal caps do not
  imply equal CPU effort or an optimal comparison algorithm.

* JSON documents use an explicit field allowlist and reject duplicate keys. Silently ignoring an unfamiliar constraint could produce a feasible answer to a different problem. Metadata belongs outside the versioned instance/plan contract.
* Rendering consumes independently verified schedules. Actual boundary delays are distinct from directed travel, and zero-length service is a marker rather than an invented interval. Replayed historical schedules describe the model, not an unavailable timestamped execution log.
