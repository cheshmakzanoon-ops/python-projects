# Reproducible measurements

The accepted standard run passed on CPython 3.14.8 at source commit
`ec1d0106df086a48923016c33199cfbda0aebbc0`, in a clean, isolated Linux checkout.
The [raw benchmark report](../../../docs/evidence/final/standard/routecraft-3.14.8-benchmark-benchmark.json)
contains every trial; the [verification wrapper](../../../docs/evidence/final/standard/routecraft-3.14.8.json)
records commands, immutable source inputs, exit codes and unchanged-source checks.
The benchmark command took 709.636 seconds including warmups, checks and reporting.
These measurements concern synthetic island deliveries, not real roads.

Run `python -m pp_routecraft.cli benchmark --profile ci|standard --output ABS
--seed 1729`. Standard retains 18 scale scenarios: 25, 100 and 500 customers;
seeds 1729, 1730 and 1731; and loose/tight window regimes. Each algorithm receives
one warmup and five measured trials per scenario. Both algorithms found verified
plans in all 180 measured scale trials. All 90 paired scale comparisons were gains
for search, with the same vehicle count within every pair. CI uses two 25-stop
scenarios and shorter iteration budgets; its accepted runs on both interpreters
published six gains and four losses rather than concealing the losses.

| Customers | Fleet used | Baseline/search median seconds | Search iterations | Median paired travel reduction | Reduction range |
| --- | --- | --- | --- | --- | --- |
| 25 | 4 | 0.120 / 0.122 | 60 | 20.71% | 8.14–27.23% |
| 100 | 13 | 1.015 / 2.041 | 30–52 | 31.23% | 20.03–35.67% |
| 500 | 62, 63 or 66 | 8.132 / 8.056 | 29–60 | 9.73% | 0.21–14.00% |

Each tier aggregates 30 measured pairs. Percentages compare travel within each
pair, then take the median; they do not aggregate unlike fleet objectives into
one scalar. Median time to first feasible search plan was 1.805 ms, 16.714 ms and
337.054 ms respectively. The median of the six scenario-level verifier medians
was 0.0866 ms, 0.6672 ms and 11.8115 ms. Process peak RSS was 81,141,760 bytes,
a cumulative high-water mark including imports and warmups, not isolated solver
allocations. CPU model and memory limit were unavailable and remain explicitly
unknown/null in the raw report.

Standard gives each algorithm a 60-iteration cap and respective wall allowances
of 0.4, 2 and 8 seconds. A baseline iteration reconstructs a plan; a search
iteration executes a neighborhood. Both include an initial construction and
record actual effort. Equal caps do not imply equal CPU work. Baseline completed
60 restarts for 25/100 stops and 14–26 for 500. Search exhausted 60 iterations in
all 25-stop trials, stopped at the wall boundary in all 100-stop trials, and
stopped by wall/iteration limits in 26/4 of the 500-stop trials.

Deadlines are cooperative at atomic-operation boundaries. **86 of 180 measured
scale algorithm trials exceeded their wall allowance.** The largest observed
100-stop search duration was 2.080 s against 2 s; at 500 stops, search reached
8.554 s and baseline reconstruction reached 10.839 s against 8 s. These are actual
operation overruns, not strict timeout compliance or realtime guarantees. The
incumbent is retained. Wall timing can change completed iterations and the plan;
iteration-only deterministic tests are separate.

Both profiles also include a separate tiny control in `metrics.controls`, outside
the scale-case counts. Independent exhaustive enumeration checked 24 labeled
plans and proved objective `(1, 8)`. Construction already achieves that optimum.
One real paired warmup and five actual baseline/search pairs each executed all
20 iterations; every plan was independently verified, and all five comparisons
were measured ties. The report includes the oracle plan, input digest, effort,
times and trajectories. This establishes genuine non-improvement on that tiny
instance, not optimality on the scale scenarios. A negative regression injects a
valid but suboptimal baseline and requires rejection instead of a manufactured tie.
The earlier standard attempt without this control is preserved under the root
`attempts/routecraft-missing-control` directory and is superseded for acceptance.

Replanning, exact feasible/infeasible tiny fixtures, source stability and every
scale search-plan check also passed in the accepted run. The seeded demo improved
construction `(4,999)` to `(4,657)`, rejected a duplicated stop and produced an
independently verified new-request plan `(4,606)` with actual maps/timelines.
The latter is a different instance, not a comparable improvement ratio.

Provenance has two deliberately distinct scopes. The raw application report uses
its documented project/docs digest
`36ababf28a3a00a087fcae837c06ef1370f30928c011e2db64d0bf03f5585685`
and a four-file root digest. The outer wrapper enumerates its own code/test/lock
inputs, excludes descriptive evidence/docs, and records source digest
`75771d0bde227d959163d644c0ffd95ed62cfc4c4e53b4ad337ef2679bc325ee`
and root-contract digest
`b6cd5e99e80442d13aa0c3b7d6c7423f181f6572242dab63f8f2d9f2597be363`.
These hashes are not interchangeable. Both record the measured clean commit and
check their scopes for stability. The lock hash is
`9aef9e96a988bfdd7403447241e67af694abf1c7d3910e57cae691e55643a011`.
The synthetic scale dataset ID is
`island-v1:47bdf3cc326ba4750d80d6b206ac26afb53390675aa11ee40240ced618f89638`.
Later docs-only summaries do not rewrite those measured artifacts.

Large-instance optimality gaps remain unknown. Fleet capacity is generous, and
the synthetic window regimes need not bind every route. No production capacity,
live traffic, universal heuristic dominance, strict latency bound, or global
optimum is inferred. Standard measurements run serially with BLAS/OpenMP threads
set to one. Original heuristics, their verifier and tiny oracle remain available
through the installed Python API; no solver wrapper supplies these results.
