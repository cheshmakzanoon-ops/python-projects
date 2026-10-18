# Reproducible measurements

`python -m pp_routecraft.cli benchmark --profile ci|standard --output ABS --seed
1729` writes `benchmark.json`. CI includes two 25-stop scenarios (loose and tight
windows), exact feasible/infeasible tiny fixtures, and a real new-request rolling
scenario. Standard includes 25, 100 and 500 stops, three seeded instances per tier,
and both window regimes. Each algorithm receives one warmup and five measured
runs per scenario. The constructor baseline receives randomized greedy restarts;
the authored adaptive search begins from greedy then uses its original moves.

Both algorithms receive identical iteration caps and wall allowances; all actual
counts, elapsed times and stopping reasons remain in JSON. A baseline iteration
is one full construction restart and a search iteration one neighborhood. Atomic
operations may overrun a deadline. This is an honest effort-capped comparison,
not a claim of identical instruction counts. Seeds advance between paired repeats;
wall timing can alter completed iterations and therefore the resulting plan.
Iteration-only deterministic tests are separate.

Both profiles also run a **separate tiny non-improvement control**, recorded in
`metrics.controls` rather than mixed into the 2 CI or 18 standard scale cases.
The directed three-customer fixture has an independently exhaustively proven
optimum. Its greedy construction already reaches that optimum. One actual paired
warmup and five actual baseline/search measurements still execute the full
20-iteration budget, with independently verified plans. The report records the
oracle objective/plan/enumeration effort, individual measured durations and effort,
and comparisons computed from actual trial objectives. Five ties demonstrate a
real case in which search finds no improvement; they are not evidence that a
larger island instance is optimal. A mismatched or invalid control plan fails the
benchmark rather than manufacturing a tie. The existing scale-case inputs, seeds,
budgets and dataset digest remain unchanged; the control has its own input digest.

Metrics include paired gains/ties/losses/unavailable results, feasible rates,
lexicographic objectives, time to first feasible, best improvement trajectory,
operator counts, verifier median latency and Linux process peak RSS. RSS is a
cumulative high-water mark including imports and warmups, not an isolated
allocation measurement. CPU model and memory limit are explicitly unknown when
unavailable; Python/OS, source commit/dirty state, project/root/lock digests and
exact input digest identify the run. Input data are synthetic, not production
routing workloads or road-network performance claims.

Digest inputs: project packaging/config, README, src, tests, benchmarks, examples,
and docs excluding status/evidence; root AGENTS, Ruff config, portfolio manifest
and dispatcher. Generated artifacts, caches, bytecode and output JSON are excluded
to avoid self-reference. Source/root digests are checked again after a run.

Local preliminary demo (seed 1729) produced a verified objective `(4,657)` and a
new-request replanned objective `(4,606)`. These objectives concern different
instances and are **not** a claimed replanning improvement ratio. Standard timing
claims await the coordinator's committed, serial benchmark artifact. No fabricated
throughput, best-known gap or global optimality claim is made.

The [development evidence directory](evidence/README.md) records local checks;
coordinator verification supplies the final committed-snapshot and standard run.
