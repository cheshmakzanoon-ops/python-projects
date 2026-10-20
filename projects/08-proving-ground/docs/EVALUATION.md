# Evaluation and uncertainty contract

## What is scored

`evaluate(store, data, split, artifact_digest, ...)` verifies and loads the
persisted artifact. Its declared dataset, split, and ordered sensor names must
match the supplied input. The evaluator scores those loaded bytes, rather than
a mutable `TrainingResult` bearing an unrelated caller-supplied digest. Reports
are schema version 2. A schema-v1 report can be read as history but cannot be
registered or promoted as current evidence.

The validation policy is frozen separately from the resulting metrics.
`validation-artifact-v2` preserves the demonstration's numeric thresholds:

| Requirement | Default |
| --- | ---: |
| Validation rows | at least 100 |
| Positive and negative rows | at least 10 each |
| Average precision | at least 0.35 |
| ROC-AUC | at least 0.65 |
| Brier score | at most 0.20 |

These thresholds are examples chosen for the synthetic task. They are not a
real-equipment approval policy. Class counts and class balance must agree;
required numeric values must be finite and within their mathematical ranges.
Neither test-role reports nor undefined one-class discrimination can authorize
a deployment. Slices, calibration, and bootstrap intervals are descriptive and
are not extra unannounced gates.

## Point estimates

For labels `y_i` and probabilities `p_i`, Brier score is
`sum((p_i - y_i)**2) / n`. ROC-AUC is the fraction of positive/negative pairs
ordered correctly, with one half for tied scores. Both discrimination metrics
are deliberately reported undefined unless both classes occur.

`pr_auc` means **average precision**, not trapezoidal integration of a plotted
precision-recall curve. At descending distinct score thresholds `s_j`, let
`a_j` be the positives with score exactly `s_j`, and `b_j` all rows with that
score. With cumulative counts `A_j=sum(a_0..a_j)` and `B_j=sum(b_0..b_j)`:

```text
AP = sum_j ((A_j / B_j) * (a_j / P)),  P = sum_j a_j
```

All tied scores enter together. Sorting individual tied rows arbitrarily would
change precision and produce the wrong statistic. Zero-weight thresholds in a
bootstrap draw contribute zero; an empty prefix has precision zero.

Calibration has ten fixed probability bins. Bin `j` covers `[j/10,(j+1)/10)`,
with probability 1 included in bin 9. Each records its count, mean prediction,
and observed fault rate. An empty bin records null summaries. Asset-modulo and
sensor-missingness slices are fixed without consulting labels; fewer than 100
rows is flagged as insufficient for that descriptive slice.

## Whole-asset bootstrap

Rows within an asset are correlated. A bootstrap draw samples `U` asset IDs with
replacement from the `U` observed assets and includes every row of each sampled
asset, including duplicates. This is a conditional resampling description of one
fleet, not an estimate of every source of uncertainty in a new fleet.

The implementation represents the draw as multiplicities `m_u`. A row belonging
to asset `u` has integer weight `m_u`. At each tied score it sums those weights
separately for positives and all rows, then evaluates the AP formula above.
This gives the same statistic as physically expanding the sampled rows.

For example, a fleet with assets `a`, `b`, and `c` and draw `[a,a,b]` assigns
weights 2 to every observation of `a`, 1 to every observation of `b`, and 0 to
every observation of `c`. If all observations of `b`
share a score with some observations of `a`, the weighted counts still enter at
one threshold. Resampling individual rows or breaking that tie is a different
statistical procedure.

`ClusteredAveragePrecision.prepare` builds asset and score indices once.
For `n` rows, `U` assets, `G` distinct scores, and `R` repetitions:

| Work | Bound |
| --- | --- |
| Initial indexing and ordering | `O(n log n)` |
| Each draw: multiplicities, weighted counts, cumulative sums | `O(U + n + G)` |
| Stored plan and temporary vectors | `O(n + U + G)` |
| Repeated score sorting or duplicate-row index expansion | none |

The previous implementation scanned all rows separately for each asset and
expanded and sorted sampled rows on every repetition. The bounded workload in
[BENCHMARKS.md](BENCHMARKS.md) records this work directly; wall time is not a test
assertion. Ordinary tests enumerate tiny cluster draws and derive AP with exact
`fractions.Fraction` threshold counts, independently of this vectorized method.

## Percentiles and scientific limits

The seeded generator samples assets in sorted-ID order. The report retains the
seed, repetitions, defined and undefined counts, number of assets, row count,
score groups, and algorithm identifier. It takes NumPy's default linear 2.5th
and 97.5th percentiles of **defined** AP draws.

A draw missing either class is excluded and counted as undefined. The interval
therefore conditions on both classes appearing; it is not an unconditional
confidence statement. If no draws are defined, both endpoints are null. A single
asset or almost homogeneous clusters can yield degenerate or selective intervals.
There is no minimum independent-asset count in the promotion gate. Row/class
minimums alone do not establish independent observations or adequate fleet
coverage. Small slices, few assets, selection among candidates, and synthetic
outcomes all limit inference. The final held-out test report is descriptive
postselection evidence and must not be used to retune these gates.
