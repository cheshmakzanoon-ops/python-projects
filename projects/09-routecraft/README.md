# Routecraft

Routecraft solves vehicle-routing problems with directed travel times, capacity limits, service-start windows, service durations, and depot-return shifts. Its insertion and neighborhood search produce candidate plans; a separate verifier recomputes every schedule, cargo balance, directed arc, and objective. A small exhaustive solver supplies exact answers for up to six customers and two vehicles.

The objective is lexicographic: use fewer vehicles first, then reduce total directed travel. A heuristic answer is `FEASIBLE` or `NO_FEASIBLE_PLAN_FOUND`. Only exhaustive enumeration establishes `OPTIMAL` or `PROVEN_INFEASIBLE`; the large-instance optimality gap is unknown.

## Run and inspect a plan

From this project directory, using uv 0.12.23:

```sh
uv sync --locked --python 3.14.8
uv run --locked --python 3.14.8 python -m pp_routecraft.cli demo --output /tmp/routecraft-demo --seed 1729
uv run --locked --python 3.14.8 python -m pp_routecraft.cli verify \
  --instance /tmp/routecraft-demo/replanned-instance.json \
  --plan /tmp/routecraft-demo/replanned-plan.json
```

The demo constructs and improves 25 synthetic deliveries, records rejection of a deliberately duplicated stop, and adds a new request after one vehicle has completed a service. That vehicle keeps its remaining cargo; an unstarted vehicle must load the new job.

Inspect `demo.json`, `plan.json`, `routes.svg`, and `timeline.svg`, then the corresponding `replanned-` files. Route maps show directed order; coordinates are visual aids rather than road geometry. Timeline legends distinguish travel, window waiting, service, and delay at the actual replanning boundary. Zero-duration service is a tick rather than a fabricated interval.

Outputs require an absolute directory that is empty or bears the exact Routecraft ownership marker. Cleanup removes fixed owned filenames and preserves unrelated files:

```sh
uv run --locked --python 3.14.8 python -m pp_routecraft.cli clean-demo --output /tmp/routecraft-demo
```

## Python API

```python
from pp_routecraft import SearchBudget, solve, verify
from pp_routecraft.fixtures import island

instance = island(25, seed=1729)
result = solve(instance, SearchBudget(iterations=100), seed=1729)
if result.plan is not None:
    report = verify(instance, result.plan)
    assert report.valid
    print(report.objective)  # (vehicles used, total directed travel)
else:
    print(result.status, result.stopping_reason)
```

Iteration budgets are reproducible for equal inputs, seeds, and package versions. Wall-clock limits and cancellation are cooperative at completed-operation boundaries; an insertion or repair can overrun the requested deadline. A stop observation prevents further work and retains any verified incumbent.

`generate`, `solve`, `verify`, `replan`, and `compare` expose the individual steps; use `COMMAND --help` for arguments. The [JSON format](docs/FORMAT.md) specifies supported fields and units. Unknown fields, duplicate object keys, and unsupported versions fail explicitly rather than silently dropping constraints.

## Development and limits

```sh
uv run --locked --python 3.14.8 ruff format --check .
uv run --locked --python 3.14.8 ruff check .
uv run --locked --python 3.14.8 mypy src
uv run --locked --python 3.14.8 pytest
uv build --python 3.14.8
```

Python 3.13.16 is also supported in a separate environment. The solver requires no service, external routing API, credentials, or paid dataset. It uses standard-library algorithms; Matplotlib renders reports. Benchmarks were measured on Linux with synthetic instances. Replanning requires a named departure/service-completion boundary and prohibits cargo transfers, reloading, live traffic changes, and mid-edge snapshots.

Read [architecture](docs/ARCHITECTURE.md), [design decisions](docs/DECISIONS.md), [operations](docs/OPERATIONS.md), [acceptance](docs/ACCEPTANCE.md), [verification](docs/VERIFICATION.md), and [benchmarks](docs/BENCHMARKS.md) for contracts and evidence. The [case study](docs/CASE_STUDY.md) explains tradeoffs; [sample artifacts](artifacts/README.md) retain their historical source provenance. [Third-party notices](docs/THIRD_PARTY.md) record dependencies and asset origin.
