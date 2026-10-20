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

## Construction and insertion certificates

Greedy insertion chooses the smallest feasible `(new vehicles, travel increase)`
for the next due-order job. Regret insertion considers the first eight pending
jobs, prioritizing scarcity and the difference between the best and second-best
insertion. It is bounded lookahead, not an exhaustive regret scan. Ties use the
vehicle's input position, then insertion position; cached profiles do not change
that ordering or consume randomness.

`construction/profile.py` stores a feasible route's earliest departures and latest
service starts. For a customer `i` followed by `j`, its latest start is
`min(due[i], latest[j] - service[i] - travel[i][j])`. The last customer uses the
vehicle's return deadline in place of `latest[j]`. These backward thresholds
include every remaining window, service duration and the directed depot return.

Inserting `x` between `a` and `b` computes its service start from the cached
departure of `a`. At the frozen-prefix boundary that departure is the actual
snapshot time. The insertion is feasible exactly when `x` meets its window and
its departure plus `travel[x][b]` meets `b`'s latest threshold, or the depot
deadline at the route end. Load/manifest eligibility is checked separately.
Its travel change is exactly `travel[a][x] + travel[x][b] - travel[a][b]`;
this does not assume symmetric or metric travel. The unchanged suffix keeps its
direction. Route reversal and block moves continue to reschedule their complete
directed routes; the insertion formula is not a two-opt shortcut.

Repair retains profiles for unchanged routes and rebuilds only the route receiving
a delivery. Each position check uses constant work; selecting the best one or two
choices is linear, without constructing every candidate schedule. A feasible
route of length `r` needs `O(r)` profile work and `O(r)` insertion-position work,
replacing `O(r²)` schedule work and candidate schedule storage. For one broad-window
route built from `n` deliveries, complete schedule work is `O(n²)` rather than
`O(n³)`. This is an operation bound, not a total memory or latency guarantee.
The independent verifier still recomputes every complete published candidate.

An arbitrary directed matrix may violate the triangle inequality: an incomplete
route can miss its depot deadline even though inserting an onboard stop makes
the route feasible. Such a route has no usable timing certificate. Repair falls
back to full scheduling of its insertions, comparing travel against the raw
original arcs rather than discarding the route. This exceptional path retains
`O(r²)` work per job/route. Heuristic construction remains incomplete: a tour
requiring several jointly inserted stops may have no feasible intermediate tour.

## Search and stop boundaries

Search retains an immutable best incumbent separately from its accepted current
plan. It selects relocation, swap, reversal, random destroy, directed-nearby
destroy, two-route suffix exchange, or short block exchange using seeded adaptive weights. Repair uses regret insertion. Improvements
receive weight reward; exponential smoothing updates each used operator.
Annealing can accept greater travel on the same number of vehicles. It never
accepts a hard violation; every complete candidate passes the independent
verifier. Reversal recomputes internal **directed** arcs. Iteration mode is
reproducible for equal input, seed, package versions and budget. Wall-clock mode
reports actual iterations and makes no deterministic-count promise. Cancellation
is latched when observed; both construction attempts and every search iteration
check the stop boundary before doing more work. A final observation also runs
when no next iteration exists, including a zero-iteration construction. A deadline
or cancellation during the last atomic operation is reported as such; that
operation's verified incumbent is retained. Cancellation takes precedence over a
simultaneously observed wall deadline. Completed iterations include rejected or
infeasible moves, and operator counts sum to that number. Initial construction
is outside the iteration count but inside the wall allowance.

## Independent checks and exact proof

`reference/exhaustive.py` enumerates every customer permutation and every weak
composition of its length into labeled vehicle routes. It independently computes
arc objective, capacity and time feasibility. Its timing formula accumulates
travel/service without waiting and retains the maximum ready-time deficit over
each path prefix; it does not call the production scheduler or verifier for each
candidate. The final exact incumbent must also pass the verifier, and disagreement
raises an internal error rather than returning an optimality claim. The domain
is <=6 customers, <=2 vehicles and no rolling state. It proves infeasibility only
after exhaustion. The production heuristic does not call the oracle.

Generated tests use a third method: assign customers to labeled vehicles first,
permute each assigned route, then simulate directly. They compare both accepted
and rejected plans with the verifier, and compare the optimum/infeasibility with
the exact reference. Separate insertion tests compare every position against
unindexed simulation with asymmetric/zero arcs, windows, services, capacities,
partial manifests, frozen prefixes and delayed actual departures.

## Rolling state and cargo ownership

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
units. Unknown fields, duplicate object keys, and unsupported versions fail. A misspelled or future constraint is never silently ignored. The [format reference](FORMAT.md) lists accepted objects and defaults. `instance.json` and `plan.json` round-trip
through strict parsers; no pickle or executable format is used. Future incompatible
formats require a new schema version. Reports come from verified schedules;
synthetic x/y geometry never substitutes for matrix costs.
