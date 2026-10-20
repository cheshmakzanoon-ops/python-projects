# Core correctness and bounded workload review

This review compares exported commit `39d3a8d` with the revised working-tree
Python package. The original acceptance artifacts remain unchanged. New evidence
is scoped to authored signals, exact arithmetic and controlled state schedules;
it does not establish real-recording accuracy.

## Reproduced failures and design repairs

| Baseline behavior | Revised behavior and independent check |
| --- | --- |
| CMND at energy scale `1e-30` becomes all ones; analytic 440 Hz at amplitude `1e-15` is unvoiced even with silence RMS `1e-18` | Positive cumulative energy is normalized without an absolute epsilon; algebraic ratios and analytic frequency at both sample rates are invariant within tolerance |
| A unit flux peak at frame 10 disappears after appending an unrelated peak of 100 at frame 60 | Relative-peak and median floors share a ±8-frame neighborhood; appending beyond that horizon preserves the earlier event |
| A confidence-.1 onset cannot split a note but still moves its start to sample 6000 | Splitting, snapping and reattack all use confidence ≥.5; adding a weak event leaves the note record unchanged |
| Input is not copied until first iteration; caller mutation changes accepted audio | Feed copies immediately; the returned batch owns iteration until drained/closed |
| Closing after a yielded frame leaves its timestamp uncommitted; a subsequent flush replays it | State advances before exposing a frame; direct padded-grid and partial-consumption schedules check every start/sample |
| Interrupted final iteration permits appending new input | Finalization is irreversible; only an empty final feed may resume pending frames |
| Returning only one of 47 eligible frames changes challenge eligibility from 47 to 1 and reports recall 1.0 | Independent input count/hop define all 47; one estimate reports recall `1/47`, with missing-output counts |
| No matched events reports zero onset/pitch error | Undefined conditional errors are null, accompanied by numeric misses/extras |
| The renderer can plot one array while embedding a different recording | Captured WAV is decoded and matched exactly to plot samples/rate before figure allocation; JSON/HTML share its encoded-byte digest and scope |

The [baseline failure capture](../artifacts/deep-core-baseline-failures.txt)
contains eight failing numerical/ownership cases and one plot/playback mismatch
case against the exported package. The raw
baseline workload below also captures the denominator defect through its old
API, avoiding an inference from a changed function signature. The revised
`trajectory_metrics` deliberately requires `sample_count`; callers must pass
the actual framing configuration. [OPERATIONS.md](OPERATIONS.md) gives migration
examples, and [METHODOLOGY.md](METHODOLOGY.md) states metric populations and null
semantics.

Removing a recording-global floor initially exposed tiny periodic RMS increases
as false attacks in the six-pluck acceptance fixture. The repair uses a centered
three-frame mean of RMS before the rising-envelope gate. This addresses the
mechanism instead of reinstating a future-dependent threshold or weakening the
fixed clean gate. Attack decisions still fit within the declared ±8-frame horizon.

## Alignment responsibilities and independent oracle

The edit objective is preserved: gap 1.2; nominal pitch difference 1.5 per
semitone; timing penalty in seconds capped at 2; uncertainty penalty 3. An
exhaustive test generates every monotone edit path for 40 seeded problems and
scores each directly, separately from the production recurrence. Explicit cases
cover exact ties, empty inputs, gap order and caller-specified tempo. Returned
notes are consumed exactly once and in order.

The baseline stored floating scores and one-byte operations for all cells,
and created a tiny NumPy argmin input for each cell. Revised alignment retains
two cost rows plus one-byte traceback and uses scalar comparisons. Exact ties
retain the match/deletion/insertion priority. Traceback calculates local match
cost directly, avoiding cancellation in cumulative-score subtraction. The time
complexity remains quadratic; matrix payload drops from nine to one byte per
cell plus the linear Python rows. The checked 4,000,000-cell budget remains in
effect.

## Fixed workload and raw results

[The workload](../benchmarks/core_review.py) is identical for both package
snapshots. It runs alignment sizes 100×92, 300×277 and 600×554, with three
measurements each, then one 12-second synthetic phrase. No 60/600-second profile
was rerun. Runs use CPython 3.14.8, one process and numerical thread counts of one
on a shared host. They are bounded mechanism measurements, not an exclusive
throughput benchmark.

| Reference × detected | Cells including boundaries | Baseline median, seconds | Revised median, seconds |
| --- | --- | --- | --- |
| 100 × 92 | 9,393 | 0.0281849650 | 0.0035528790 |
| 300 × 277 | 83,678 | 0.2476575900 | 0.0306725520 |
| 600 × 554 | 333,555 | 0.8725203620 | 0.1250271200 |

The largest measured alignment is about 7.0 times faster for this input.
Reference/detected/timing/cents mapping digests are identical across snapshots
at all three sizes. Recomputed local costs differ only at floating summation
roundoff from the baseline cumulative subtraction.

The phrase uses 14 harmonic plucks, alternating amplitudes .06/.6, noise standard
deviation .0005, seed 1729, 48 kHz, frames/hop/block 2048/256/8192, authored bends,
vibrato and onset perturbations. Both snapshots produce 14 notes and 14 onsets;
all 709 predeclared eligible centers are voiced within 10 cents of the analytic
instantaneous frequency. Both retain at most 9,984 input samples. The single
phrase run has no warmup and takes 0.3107096430 s baseline and 0.3958439230 s
revised. This single noisy observation does not demonstrate an analysis-pipeline
speed improvement. Alignment is the measured optimization; the other changes
repair semantics and reporting.

Raw reports include each repetition, exact tone parameters, source package path,
Python-code content hash, workload hash, dataset hashes and semantic witnesses:

- [Baseline package `39d3a8d`](../artifacts/deep-core-baseline-39d3a8d.json)
- [Revised package](../artifacts/deep-core-review.json)

The shared workload SHA-256 is
`24cff444860775f172a48910620ade1e2bf0fe9784afc914794778ec7e789879`.
The baseline Python-code hash is
`c208e151c67a774a303f6d7e43af1ea36b8f97292e762f35dfd30a6335ea2aeb`;
the revised hash is
`fbd4f7e07615cff14f69239b081101ea2ea2501d1b5d4e6a305dba241bf438af`.
These hashes cover the listed Python scope, not an immutable whole-repository
release or the historical standard benchmark's broader source scope.

## Reproduction

Run from the repository root to export the historical package without changing
the checkout:

```sh
mkdir -p /tmp/resonance-baseline
git archive 39d3a8d projects/10-resonance/src | tar -x -C /tmp/resonance-baseline
cd projects/10-resonance
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLCONFIGDIR=/tmp/resonance-matplotlib
PYTHONPATH=/tmp/resonance-baseline/projects/10-resonance/src \
  .venv/bin/python benchmarks/core_review.py --output /tmp/resonance-before.json
.venv/bin/python benchmarks/core_review.py --output /tmp/resonance-after.json
```

Use the locked 3.14.8 environment and run snapshots sequentially. Confirm matching
workload/dataset hashes before comparing timings or mappings. To reproduce the
eight numerical/ownership baseline failures, set the same `PYTHONPATH` and run:

```sh
.venv/bin/python -m pytest -q tests/unit/test_core_semantics.py \
  -k 'not trajectory and not evaluator and not partial'
.venv/bin/python -m pytest -q \
  tests/integration/test_core_exports.py::test_report_rejects_playback_that_does_not_match_the_figure
```

Current full-suite, wheel and compatibility results are in
[VERIFICATION.md](VERIFICATION.md). The independent MIDI tests reconstruct exact
rational seconds at two rates and four tempos; playback tests compare encoded
bytes, JSON metadata and decoded sample count. These are correctness witnesses
with explicit units, not a claim that any single test certifies musical quality.
