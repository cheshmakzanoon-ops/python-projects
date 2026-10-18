# A09 Routecraft status

Status: verifying
Phase: P4/P5 stable worker handoff; implementation writes paused.

Project source snapshot: development Git HEAD
`703bf365454a4bad657dac87a973f2b3bdea8ea2`, project dirty=true.
Routecraft-defined source SHA-256:
`f716e8fc03430a1af12faba37cd96210a644caed5afe6dcfa5e0c255f493d520`.
Lock SHA-256:
`9aef9e96a988bfdd7403447241e67af694abf1c7d3910e57cae691e55643a011`.
This is a measured development snapshot, not a final immutable release claim.

Implemented: immutable integer-unit domain; independent input/plan/schedule/load/
objective verifier; original greedy and bounded-regret insertion; directed
relocation, swap, reversal, random/related destroy-repair; adaptive operator
weights and annealing with separately retained incumbent; independent exhaustive
reference through 6 customers/2 vehicles; historical-prefix/actual-time/cargo-safe
rolling replanning; strict JSON, public CLI and actual SVG maps/timelines;
equal-cap baseline comparison with warmup + 5 measured repetitions and source
metadata. All source and edits are restricted to this project. No worker Git or
shared-root mutations.

Local acceptance:
- RC-01: hand-derived objectives (1,8) and (1,7), 5040 six-customer labeled plans,
  infeasibility reference and generated directed-matrix oracle bounds pass.
- RC-02: duplicate/missing/unknown stops, capacity, windows, service/return shifts,
  and objective/return/schedule cache corruption are independently rejected.
- RC-03: forward cost8 vs reversed cost30 and arrivals6,14,23; directed move
  schedules checked independently.
- RC-04: injected invalid moves, callback cancellation, zero deadline and
  cancellation after progress retain a valid best incumbent.
- RC-05: same seed/input iteration results reproduce exact plans, trajectory,
  operator counts and actual80 iterations.
- RC-06: local CI comparison passes, 5 paired runs for loose/tight25 stops;
  standard25/100/500 multi-seed run remains coordinator-owned and pending.
- RC-07: actual boundary delay, new request on idle fleet, frozen history,
  manifest/transfer/unloaded-cargo/matrix/mid-edge failures and monotone repeated
  replanning tests pass.
- RC-08: strict JSON roundtrip, externally invoked CLI demo/solve/verify/replan,
  real maps/timelines, truthful unknown vs exhaustive infeasibility, stale-plan
  removal and refusal to publish unverified JSON pass.

Verified commands (uv0.12.23; BLAS/OpenMP threads1):
- `uv sync --locked --python 3.13.16`: exit0.
- Explicit3.13.16 `ruff format --check .`, `ruff check .`, `mypy src`: exit0;
  strict mypy21 source files.
- Explicit3.13.16 `pytest -q --cov=pp_routecraft --cov-branch`: 73passed in43.64s;
  branch-enabled overall coverage93.38896020539153%.
- `uv build --no-sources --python 3.13.16`: sdist+wheel passed.
- `uv sync --locked --python 3.14.8`: exit0, dependency wheels available.
- Explicit3.14.8 full format/lint/strict mypy/test/build: 73passed in23.10s;
  branch-enabled overall coverage93.20580474934037%.
- `python ../../scripts/wheel_smoke.py /workspace/python-projects/projects/09-routecraft pp_routecraft`:
  exit0; locked-dependency wheel installed in a fresh3.14.8 venv outside source,
  actual package path under site-packages, full demo and owned cleanup passed.
- Default3.14.8 `python -m pp_routecraft.cli benchmark --profile ci --output /workspace/.results/routecraft-ci-final-dev --seed 1729`:
  passed;10/10 search and10/10 baseline trials feasible; paired gains6/losses4,
  no losses hidden; median verifier ~89microseconds on this synthetic25-stop input.
- Final3.14.8 format/lint/mypy checks after evidence generation: exit0.

Default .python-version is3.14.8; required supported interpreter paths remain
3.13.16 and3.14.8. No service, external credential, solver package or paid data.

Artifacts:
- `docs/evidence/development-summary.json`: small actual dual-interpreter,
  wheel/hash and CI measurements; explicitly development dirty snapshot.
- `artifacts/`: actual tiny JSON/verified map/timeline and source/file manifest.
- /workspace/.results/routecraft-dev: actual25-stop demo, objective(4,657),
  new-request plan(4,606), intentionally rejected duplicate and visual reports.
- /workspace/.results/routecraft-ci-final-dev/benchmark.json: full CI measurements.
- /workspace/.results/routecraft-coverage-313.json and -314.json: full coverage.

Most serious defect found in review: a second rolling update could reset a
previously started vehicle and shorten its frozen prefix. Added monotone
started/prefix/time checks and a repeated-replan regression. Two earlier tiny
replan fixture failures were infeasible23-unit new-request roundtrips on20-unit
shifts; extended only replanning test shifts to100 instead of weakening rules.

Remaining required work: coordinator read-only review, committed-source immutable
verification and serial standard benchmark. Worker has NOT started a standard
benchmark. No external blocker. Current active edits: none; stable for commit.
Next action: coordinator commits source and runs standard under its exclusive
lease, then supplies any review/measurement correction request. No optional
OR-Tools, reloading, transfers, live roads, mid-edge or traffic updates claimed.

## Independent review correction (authoritative latest snapshot)

Status: verifying; correction complete and writes paused again.
Current development HEAD: `ddd1638d01e3f309c2c7826086e488dd7edc463c`; dirty=True.
Current project source SHA-256: `4bc6043864f3321f2b64d594efad64245d44fed0e0865631e03cfcf6d2adac2d`.
Prior full-suite/sample/CI evidence above describes its earlier measured snapshot,
not this correction's changed source digest.

A03 reproduced a noncanonical SDK customer tuple that passed `input_errors` while
the positional optimizer disagreed with the keyed independent verifier. Customer
records must now be ordered by ascending unique matrix-node ID1..n. This is
documented explicitly. `solve`/`exhaustive` return INVALID_INPUT, `verify` rejects
and public `construct` raises ValueError before scheduling. The exact supplied
case is a regression, including the caller's valid canonical reorder and actual
service-duration/waiting schedule.

Affected verification after this fix: 61unit/property/exact/status tests passed
on3.13.16 in4.83s and3.14.8 in7.80s; format/lint/strict mypy(21files)/sdist/wheel
passed. One initial test runner hit an overlapping .venv interpreter replacement
from root onboarding; isolated UV_PROJECT_ENVIRONMENT paths resolved it. A test
expectation initially assumed completion-time tie breaking; both customer orders
have the same lexicographic objective, so the regression now allows both valid
return times and separately asserts the time-window/service calculation.

Evidence: docs/evidence/review-ordering-fix.json. No standard benchmark rerun.
Remaining: coordinator immutable full-suite/review/standard verification.
