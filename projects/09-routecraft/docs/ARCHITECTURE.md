# Architecture and contracts

`domain/instance.py` contains frozen dataclasses. Nodes are matrix indices:
depot zero and customers 1..n. The customer tuple must be in ascending ID
order, matching its matrix-node indices; noncanonical tuples are invalid input,
not an infeasible search outcome. `solve`/`exhaustive` return `INVALID_INPUT`,
`verify` returns an invalid report, and direct `construct` raises `ValueError`.
All demand, capacity, time and objective units
are nonnegative integers; deliveries have positive demand. Windows constrain
**service start**, waiting is allowed, service must finish within the shift,
and the final depot return must also finish within the shift. Vehicles load
their full planned demand at the depot and unload it at customers.

`validation/verifier.py` imports no scheduler or move/search module. It validates
inputs, route coverage and uniqueness, recomputes directed arcs, service starts,
load after every delivery, depot returns and lexicographic objective. Optional
schedule/return caches are checked for exact equality, never trusted. A complete
valid plan serves every mandatory stop once. Missing customers and hard
violations never become penalty scores. The optimizer has its own scheduler in
`construction/insertion.py`; this duplication is intentional independence.

Greedy insertion chooses the smallest feasible `(new vehicles, travel increase)`
for the next due-order job. Regret insertion considers the first eight pending
jobs, prioritizing scarcity and the difference between the best and second-best
insertion. It is bounded lookahead, not an exhaustive regret scan. Both evaluate
all positions of each eligible vehicle and recompute the affected schedule.

Search retains an immutable best incumbent separately from its accepted current
plan. It selects relocation, swap, reversal, random destroy, or directed-nearby
destroy using seeded adaptive weights. Repair uses regret insertion. Improvements
receive weight reward; exponential smoothing updates each used operator.
Annealing can accept greater travel on the same number of vehicles. It never
accepts a hard violation; every complete candidate passes the independent
verifier. Reversal recomputes internal **directed** arcs. Iteration mode is
reproducible for equal input, seed, package versions and budget. Wall-clock mode
reports actual iterations and makes no deterministic-count promise.

`reference/exhaustive.py` enumerates every customer permutation and every weak
composition of its length into labeled vehicle routes. It independently computes
arc objective, then invokes the verifier. The domain is <=6 customers, <=2
vehicles and no rolling state. It proves infeasibility only after exhaustion.
The production heuristic does not call the oracle.

`replanning/rolling.py` first verifies the previous plan, enforces monotone started/executed/time state on repeated updates, then rejects changes
to vehicles, depot, executed definitions/order, old matrix costs and matrix
version. Every vehicle supplies a `VehicleState`. A started vehicle's remaining
manifest must match its original suffix; quantity equals the delivery demand and
sum equals actual onboard quantity. New jobs can enter only unstarted vehicles.
There are no transfers, reloads, mid-edge or in-service snapshots. State time is
at least prior completed-service departure and may be later due to waiting.
Planning keeps the executed prefix and starts its suffix at the named actual
node/time with actual cargo. Historical travel contributes to the full-plan
objective; started vehicles still count even if all their deliveries completed.
`prepare_replan` is the required history-validation boundary; a bare instance
with state cannot establish the integrity of an absent historical plan.

JSON schema version 1 uses explicit arrays, dataclass field names and integer
units. Unsupported versions fail. `instance.json` and `plan.json` round-trip
through strict parsers; no pickle or executable format is used. Future incompatible
formats require a new schema version. Reports come from verified schedules;
synthetic x/y geometry never substitutes for matrix costs.
