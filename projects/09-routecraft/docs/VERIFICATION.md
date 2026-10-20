# Verification

## Core insertion, exact-reference and rolling-state review — October 20, 2026

The revised core passed complete structured project checks on Linux x86_64:

| Interpreter | Tests | Additional checks |
| --- | ---: | --- |
| CPython 3.14.8 | 147 passed in 13.05 s | Ruff format/lint, strict mypy on 22 source files, sdist/wheel builds, external runtime-only installed-wheel demo |
| CPython 3.13.16 | 147 passed in 11.58 s | Same checks, separate environment and build directory |

Both JUnit reports recorded zero failures, errors or skips. Commands were
`PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check routecraft` and the
corresponding `PORTFOLIO_PYTHON=3.13.16` invocation with
`UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/routecraft-3.13.16"`. These are working-tree
checks; final immutable-snapshot evidence is collected separately by the repository
verification workflow.

The core review reproduced a valid rolling continuation discarded by both
constructors: `0→1→2→0` costs three units within a ten-unit shift, while the frozen
prefix's direct `1→0` return costs 100. Infeasible partial routes now receive real
insertion checks rather than being pruned. The original failure is retained in
`test_core_boundaries.py`, along with controlled cancellation/deadline schedules
during construction, the last iteration, final independent verification, and a
supplied incumbent with zero iterations. The comparison baseline also checks its
final deadline boundary. Peer review caught a missing manifest exclusion in the
initial timing fast path: an idle truck ordered before the cargo owner could win
an insertion and cause construction to fail. Independent verification prevented
an invalid plan from escaping. The fast path now enforces the same no-transfer
eligibility before timing, with public greedy/regret owner-order regressions.

Insertion profiles were challenged against direct unindexed simulation on 600
seeded cases (`611271`), including nonmetric/zero arcs, service windows/durations,
partial onboard manifests, completed prefixes and delayed actual departure. A
third independently enumerated model assigns customers to labeled vehicles and
then permutes each route on 35 tiny cases (`702813`); it checks verifier acceptance
and rejection and the exact optimum/infeasibility. The exact reference itself now
uses a separate path-prefix waiting-deficit formula, with final verifier agreement
required. An additional 150 three-vehicle assignment cases (`91341`) independently
check cargo eligibility. A dense 80-customer work-bound regression guards against
rescheduling every insertion position.

A separate read-only mathematical review on both interpreters checked 10,190
insertion positions, including 2,359 feasible timing-profile bases, and 80 exact
cases covering 13,792 labeled route plans. Its final checks exercised 874
three-vehicle cargo-assignment queries, both final-verification stop schedules
and public owner-order/greedy-regret cases. No remaining disagreement was found
within those bounded inputs; this is not a completeness proof for the heuristic.

The [paired insertion diagnostic](evidence/core-insertion-2026-10-20.json) preserves
its actual dirty source digest
`cafee5831a2b70fe70838aed5e526797f271d6362cca057ab0f411834fcec5fb`, measured checkout
`cd058b59c5308b88807492c43acc6e3d93128c0b`, baseline `39d3a8d`, parameters and
counter scope. It precedes the final-verification and cargo-eligibility peer fixes;
its historical digest is not relabeled as the final source. All nine dense-route
pairs and the separate regret control returned
identical independently verified plans. [Benchmark documentation](BENCHMARKS.md)
distinguishes deterministic work counts from concurrent-development timing.
The retained reproduction driver was also executed successfully into a fresh
temporary report; its output does not replace the original evidence.

Both installed-wheel demos returned static objective `(4, 714)`, rejected the
deliberately duplicated stop and verified rolling objective `(4, 700)`, matching
the earlier seeded demonstration. New valid repair choices do not establish
general heuristic dominance. No standard
benchmark was rerun and no large-instance optimality bound is claimed. Dependencies
and the lockfile are unchanged.

## Historical interface and stopping-boundary review — October 20, 2026

The reviewed Routecraft working tree passed the complete project check on Linux x86_64:

| Interpreter | Tests | Additional checks |
| --- | ---: | --- |
| CPython 3.14.8 | 129 passed in 13.41 s | Ruff format/lint, strict mypy, sdist/wheel build, runtime-only installed-wheel demo |
| CPython 3.13.16 | 129 passed in 15.32 s | Same checks in a separate virtual environment |

Commands, from the repository root:

```sh
PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check routecraft
UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/routecraft-3.13.16" PORTFOLIO_PYTHON=3.13.16 python scripts/portfolio.py check routecraft
```

The project/docs source digest reported by `provenance()` was `02cbea943b40c9182849e80336ec452a06c5a3892407d32cd4ef078e4bc1819b`. The verification document and generated evidence are excluded from that digest to avoid self-reference. This is working-tree validation, not an immutable release or a hosted CI result. The package description changed; dependencies and the lockfile did not.

The review adds 25 regression cases covering latched cancellation, stop checks between construction attempts, symlink ancestors during output and cleanup, strict JSON fields/keys/versions, matrix-version identity, CLI failure status, and accurate report durations. Eighteen initial cases failed before their fixes, with one existing incumbent-retention case already passing; a later CLI replanning-budget case also reproduced its failure before correction. All new cases pass. The timeline was rendered and visually inspected in addition to tests that compare drawn travel durations with the independently verified objective.

Both installed-wheel demos retained a feasible four-vehicle incumbent with travel objective `714`, rejected the deliberately duplicated delivery, and verified a new-request plan with objective `(4, 700)`. These are seeded demonstration results, not a general performance comparison or a global-optimality claim. The suite exercises its existing CI-sized benchmark/control checks; the standard benchmark was not rerun.

## Historical evidence

The [earlier reliability review](../../../docs/REVIEW.md) fixed incomplete replanning-state checks, SDK integer aliases, numeric overflow and normalization of initial incumbents. Its Routecraft suite contained 103 tests on both required interpreters.

The initial clean-source compatibility records at `b3caa0e4594034ee8edf9ca05c3fd879d6fe18a2` contain 75 tests per interpreter, quality/build checks, installed-wheel execution, public demo and CI benchmark:

- [Python 3.13.16](../../../docs/evidence/final/python313/routecraft-3.13.16.json)
- [Python 3.14.8](../../../docs/evidence/final/python314/routecraft-3.14.8.json)

The [corrected standard execution](../../../docs/evidence/final/standard/routecraft-3.14.8.json) and [raw report](../../../docs/evidence/final/standard/routecraft-3.14.8-benchmark-benchmark.json) record source `ec1d0106df086a48923016c33199cfbda0aebbc0`. They contain 18 scale scenarios, 90 paired comparisons, 180 feasible scale algorithm trials, and a separate exact-optimal control with five measured ties. The [benchmark document](BENCHMARKS.md) retains measured costs, source scopes, outcomes and observed cooperative deadline overruns. These records do not certify later changes.

[Acceptance](ACCEPTANCE.md) maps RC-01 through RC-08 to tests and historical evidence. Sample JSON and SVG artifacts retain their original development-snapshot manifest rather than being relabeled as current output.

## Limits

The heuristic has no general optimality bound or completeness guarantee. Deadlines are cooperative at atomic-operation boundaries. Fixtures are synthetic, and no live road, traffic, cargo-transfer, reloading or mid-edge state model is supplied. A state-bearing instance requires the history checks in `prepare_replan`; it cannot establish absent execution history by itself. Historical visits in a replanned timeline are recomputed model schedules, not a full actual timestamped execution log. Hosted CI, standard performance on the revised source, and other platforms remain unverified for this review.
