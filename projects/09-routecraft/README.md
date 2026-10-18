# Routecraft

Routecraft plans a fictional island delivery fleet with capacity, directed integer
travel times, service-start windows, service durations, and depot-return shifts.
Its Python implementation owns greedy and regret insertion, directed relocation,
swap and route reversal, and an adaptive destroy/repair search. A separate verifier
recomputes every schedule and objective; a deliberately small exhaustive solver
provides an oracle up to six customers and two vehicles.

```bash
uv sync --locked --python 3.14.8
uv run --locked python -m pp_routecraft.cli demo --output /tmp/routecraft-demo --seed 1729
uv run --locked python -m pp_routecraft.cli verify \
  --instance /tmp/routecraft-demo/replanned-instance.json \
  --plan /tmp/routecraft-demo/replanned-plan.json
uv run --locked python -m pp_routecraft.cli benchmark --profile ci \
  --output /tmp/routecraft-ci --seed 1729
```

Python 3.13.16 remains supported. Each project has its own environment; do not
create a worktree for ordinary cloud tasks. Linux is the measured benchmark
platform. The solver/library itself uses the standard library; Matplotlib draws
maps and timelines and supplies no optimization algorithms.

The demo constructs and improves 25 deliveries, deliberately duplicates a stop
and records the verifier's rejection, completes one service, accepts a new
request, and replans from the actual departure boundary. The started vehicle
retains exactly its cargo; another vehicle must load the new job. Open
`routes.svg`, `timeline.svg`, and their `replanned-` counterparts alongside
`demo.json`. Coordinates are synthetic visual aids, not real roads.

Use `generate`, `solve`, `verify`, `replan`, and `compare` for individual steps;
`python -m pp_routecraft.cli COMMAND --help` lists the arguments. `solve --exact`
is intentionally limited to tiny instances. A heuristic result is `FEASIBLE` or
`NO_FEASIBLE_PLAN_FOUND`; only full enumeration establishes `OPTIMAL` or
`PROVEN_INFEASIBLE`. The large-instance optimality gap remains **unknown**.

```python
from pp_routecraft import SearchBudget, solve, verify
from pp_routecraft.fixtures import island

instance = island(25, seed=1729)
result = solve(instance, SearchBudget(iterations=100), seed=1729)
if result.plan is not None:
    assert verify(instance, result.plan).valid
    print(result.plan.objective)  # (vehicles used, total directed travel)
```

[Architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md),
[acceptance mapping](docs/ACCEPTANCE.md), [operations](docs/OPERATIONS.md),
[measurements](docs/BENCHMARKS.md), and [case study](docs/CASE_STUDY.md) explain
contracts, evidence and limitations. No project code license has been chosen by
the repository owner; [provenance](docs/THIRD_PARTY.md) records dependencies.

[Small authentic sample artifacts](artifacts/README.md) include the independently
verified hand-checkable directed tour and actual map/timeline, with a manifest
identifying its dirty development source snapshot.
