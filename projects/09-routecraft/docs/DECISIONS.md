# Design decisions

* Independent verification duplicates scheduling logic instead of sharing a
  feasibility helper. A common helper would allow the same bug to make a route
  and its check agree. Hand-calculated asymmetric costs and exhaustive enumeration
  supply additional independent evidence.
* Lexicographic `(used vehicles, directed travel)` keeps fleet count explicit.
  No scalar penalty can promote a hard-constraint violation to feasibility.
* Directed routes are fully rescheduled for every move. A symmetric two-opt
  delta would miss every reversed internal arc. This costs CPU but keeps the
  implementation auditable; bounded regret lookahead and small capacity-limited
  routes contain the cost. A measured future optimization could cache immutable
  prefix/suffix timing with independent regression checks.
* Best and accepted-current plans are different immutable objects. Simulated
  annealing may explore worse schedules without losing the best verified answer.
  Operator weights use deterministic RNG consumption and stable tie breaking.
* Wall deadlines are cooperative at complete operator boundaries. Construction
  and repair are atomic; they may overrun the requested wall limit by one
  operation. Cancellation retains the incumbent. There is no unsafe thread kill.
* Exact enumeration is intentionally tiny and independent; it is never an
  unsupported claim of global optimality on a 500-stop heuristic result.
* Vehicle manifests name jobs, not merely spare capacity. A started truck with
  spare capacity still cannot deliver an unloaded new job. Replanning is limited
  to named service-complete/departure nodes; interpolation through an edge would
  require a different travel-state model.
* Baselines receive the same iteration and wall-clock caps, but their work unit
  is a complete seeded greedy reconstruction, while a search iteration is a
  neighborhood. Actual counts and durations are published. Equal caps do not
  imply equal CPU effort or an optimal comparison algorithm.
