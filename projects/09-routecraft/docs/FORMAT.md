# JSON interchange format

Instance and plan documents use schema version `1` and UTF-8 JSON. Every object rejects unknown fields; file readers also reject duplicate keys at every nesting level. Unsupported versions are errors. Store application metadata separately rather than attaching fields whose constraints the solver cannot enforce.

All identifiers, demand, capacity, times, travel costs, and objective values are integers. Booleans and fractional aliases are rejected. Coordinates are finite numbers used only for plotting. Domain validation follows parsing: correctly shaped JSON can still describe invalid windows, an inconsistent matrix, or an infeasible routing problem.

## Instance

| Object | Fields |
| --- | --- |
| Top level | `schema_version`, `stops`, `vehicles`, `travel`; optional `depot` (default `0`), `matrix_version` (default `synthetic-v1`), `states` (default `[]`) |
| Stop | `id`, `demand`, `ready`, `due`, `service`; optional `x`, `y` (default `0`) |
| Vehicle | `id`, `capacity`, `start`, `end` |
| Vehicle state | `vehicle_id`, `started`, `executed`, `node`, `time`, `onboard`, `loaded`, `boundary` |
| Loaded job | `stop_id`, `quantity` |

`stops` is an array ordered by contiguous IDs `1..n`. Depot ID is `0`. `travel` is a square `(n+1) × (n+1)` array with a zero diagonal and nonnegative directed costs; symmetry and the triangle inequality are not assumed. Vehicle IDs are unique nonnegative integers. `matrix_version` is a nonempty string.

Stop demand and vehicle capacity are positive. Windows constrain service start, including both bounds. Waiting is allowed; service completion and depot return must occur within the vehicle shift.

A rolling instance supplies exactly one state per vehicle, including unused vehicles. `started` is a boolean. `executed` is the completed route prefix; `node` is its final stop or depot when empty. `time` is the actual boundary time. `loaded` identifies every remaining onboard job and its quantity, whose sum equals `onboard`. `boundary` is `departure` or `service_complete`.

A state-bearing instance cannot prove historical integrity by itself. Use `prepare_replan(previous, previous_plan, expanded, states)` or the `replan` command to validate the previous plan, immutable executed definitions/order, unchanged existing matrix entries, monotone time, and retained cargo ownership. A changed matrix version requires an explicit traffic-update implementation and is currently unsupported.

## Plan

| Object | Fields |
| --- | --- |
| Top level | `schema_version`, `routes`, `objective` |
| Route | `vehicle_id`, `stops`; optional `schedule` (default `[]`), `return_time` (default `null`) |
| Visit | `stop_id`, `arrival`, `service_start`, `departure`, `onboard_after` |

`objective` is `[vehicles_used, total_directed_travel]`. A route's `stops` array includes its executed prefix when replanning. Every mandatory stop appears exactly once across the plan. Unused vehicle routes may be omitted; the solver normalizes an initial incumbent into full vehicle order internally.

Schedules and return times are optional caches. If supplied, the independent verifier requires exact equality with its recomputed values. An objective is always required and checked. A `verified` flag is neither accepted nor trusted; run `verify` against the corresponding instance.

## Results and exit codes

`result.json` records status, the optional verified plan, effort, stopping reason, timing, trajectory, operator counts, and diagnostics. A heuristic failure to find a plan is distinct from an exhaustive proof of infeasibility.

The CLI returns `0` for a completed operation, including a reported `NO_FEASIBLE_PLAN_FOUND` or `PROVEN_INFEASIBLE` result. `verify` returns `1` for an invalid plan. Malformed JSON, unsupported fields/versions, invalid solver inputs or budgets, and file errors return `2`. For an `INVALID_INPUT` solver result, `result.json` and stdout retain the diagnostic status while the process exits `2`; no plan is published.
