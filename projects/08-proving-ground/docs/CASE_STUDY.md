# A passing report for the wrong model

At baseline `39d3a8d4be3e8e2e7de85379790d68f5367d6825`, a registry could
correctly compare every stored digest and still deploy a failing candidate.
The evaluator accepted two independent arguments: an in-memory fitted pipeline
and a published artifact identity. Nothing established that they represented the
same model.

The reproduction fitted prior and logistic pipelines on the same frozen split,
published the prior, and evaluated logistic while supplying the prior's digest.
The resulting report was internally consistent and all bindings matched the
published manifest, so registration and promotion succeeded at generation 1.
The statistics belonged to logistic:

| Statistic | Submitted logistic evidence | Actual persisted prior |
| --- | ---: | ---: |
| Average precision | 0.842070 | 0.321667 |
| ROC-AUC | 0.917735 | 0.500000 |
| Brier | 0.109671 | 0.218267 |

All three prior metrics failed the unchanged default gates. A report checksum
could preserve that false attribution but could not correct it. The fixture in
`tests/fixtures/legacy-evaluation-v1.json` retains the actual baseline archive,
manifest, report, and accepted SQLite history. Its provenance and checksums are
[documented with the fixture](../tests/fixtures/README.md).

The new evaluator loads and scores verified persisted bytes. Publication also
requires the dataset, split, and ordered sensors recorded by the fitter, and
validates the serialized snapshot before making it visible. A test replaces
the caller's original prior pipeline with logistic after publication; evaluation
still reports the actual prior's failing statistics. This establishes the
boundary directly instead of asserting only that strings match.

Existing evidence needed its own repair policy. Reports are now schema 2 and
the frozen policy identity changed. Legacy registries remain read-only, even
with an explicit legacy policy. Reevaluation creates new reports from actual
artifacts in a new, undeployed registry; it preserves the original audit rather
than claiming the old decision used the new semantics. Operators can select
that target with `--registry` for training, promotion, and serving. The
[runbook](OPERATIONS.md#upgrade-legacy-evaluation-evidence) shows the dependency
on the original model store and the handling of partial failures.

The same review found ownership and work problems beneath that boundary.
Read-only NumPy flags left writable caller aliases able to change a frozen
dataset. Owned immutable buffers now preserve the input snapshot, and metadata
layout changes are rejected. Eight same-generation refresh callers previously
started eight deserializations; they now share one attempt. ASGI shutdown
previously allowed a still-running loader thread to publish afterward; terminal
close now prevents that while allowing a previously captured prediction to finish.
Registration also snapshots report bytes once so a coordinated caller metrics
update cannot make returned and persisted evaluation identities disagree.

The clustered bootstrap had a separate algorithmic cost: locating every asset
rescanned the complete dataset, and each draw expanded duplicate row indices
and reordered scores. A fixed tied-score plan plus asset multiplicities computes
the same AP statistic without those operations. Exact tiny rational models and
an independent expanded-fleet implementation check it. The bounded five-repeat
workload records 40 million membership scan values and 640,000 expanded row
indices per old run versus none of those operations in the replacement, which
orders scores once. Both implementations produced exactly the same recorded
percentile endpoints. This is a focused 20,000-row calculation; it does not
replace the historical full-lifecycle measurements below.

Real SQLite child-process exits test accepted/rejected commit boundaries, and
independent peer probes exercise tied bootstrap, legacy reassessment, competing
promotions, late loads, shutdown, and explicit target adoption. Current results
and limits are in [VERIFICATION.md](VERIFICATION.md); source licensing and
real-equipment validation remain owner decisions.

## Historical implementation and workload evidence

# Reproducible experiments with byte-variable model archives

The task was to make an ML result traceable from declared equipment features through frozen evaluation and an auditable deployment. The project owns semantic identity, split/leakage checks, validation policy, content publication, generation comparisons and serving snapshots; sklearn owns model fitting and skops supplies a constrained persistence mechanism.

A tempting design was to identify a run by the serialized model's bytes. During the first integration checks, loading and prediction parity passed, but serializing the very same fitted logistic pipeline a second time produced a different SHA-256. The test `test_loaded_pipeline_reproduces_predictions` originally assumed identical artifact IDs and failed. Skops can include internal object identities, so byte equality was not a supported reproducibility contract.

The repair separates three things: a canonical semantic experiment specification, separate timestamped retry attempts, and content identities for the actual serialized archives. Experiment identity includes data/split/code/preprocessing/estimator/parameters/seed/lock. Each archived model is immutable and hashed as written. Repeated fits and loaded pipelines are compared on held-out predictions at a fixed absolute tolerance `1e-12`. No undocumented archive normalization or weakened checksum is used.

Reproduce the regression with the integration test: serialize a fitted pipeline twice, verify both archives load and produce the same predictions, then confirm the original immutable file hash stayed unchanged. The separate seeded-retraining acceptance test fits prior/logistic/tree twice and compares their held-out outputs. This establishes the chosen numerical contract while allowing different archive IDs.

A second critical boundary is requested versus applied deployment state. Tests deliberately finish an old load after a new one, fail a new artifact load, and pause an inference request across a snapshot swap. They verify actual prediction metadata rather than only a mutable registry pointer. Rollback refers to an older model through a new applied generation. A single `current_model` variable and separately read response metadata would fail these scenarios.

The accepted compatibility suites each passed 103 tests on Python 3.13.16 and 3.14.8; the independent reviewer closed 58 checks. Historical authored-suite coverage was 93.28% statements, 81.15% whole-package branches and 86.40% across the explicitly defined domain-core branches. Accepted evidence is linked in [verification](VERIFICATION.md).

The full standard lifecycle passed from clean source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`: [raw measurements](../../../docs/evidence/final/standard/proving-ground-3.14.8-benchmark-benchmark.json) and [provenance wrapper](../../../docs/evidence/final/standard/proving-ground-3.14.8.json). It generated 250,000 rows, 40 sensors and 500 assets, then fitted all 147,000 permitted training rows for prior/logistic/tree models without downsampling. The purged split retained 46,000 validation and 49,000 test rows and excluded 8,000 observations under its declared horizon/embargo rules. Logistic validation PR-AUC was 0.862534, ROC-AUC 0.928634 and Brier 0.097157; postselection test values were 0.858205, 0.930257 and 0.093795. Validation's 100 asset-bootstrap PR-AUC percentile interval was [0.856462,0.871209].

The complete measured lifecycle took 23.953577 s and peaked at 870,920,192 bytes RSS. Five 1,000-row served batches had median 2.306749 ms and sample p95 2.744622 ms; five audited model/load/snapshot transitions took 10.310927–16.033122 ms. The prior was rejected, offline/served parity met absolute tolerance 1e-12, corrupt bytes were refused and rollback finished with requested/applied generation 8. Numerical thread settings were all 1, and source stayed unchanged. These five local timing repetitions do not establish production tail latency. Earlier dirty-state 5,000-row captures remain clearly labeled historical evidence in [BENCHMARKS](BENCHMARKS.md).

The result demonstrates local lifecycle controls on original generated data. It does not prove predictive utility on real machines, reveal undisclosed causal leakage, provide arbitrary-model sandboxing, or coordinate remote serving fleets. A justified next step is evaluating a permitted real fleet dataset with predeclared temporal/asset questions and a policy approved before held-out inspection; adding model families before that would add breadth without evidence.


Independent review found the more serious identity failure documented by `tests/integration/test_review_regressions.py`: a valid Parquet file could retain original digest metadata while fractional IDs/labels were silently truncated by NumPy conversion. The original reproduction accepted modified physical data with the old digest. The fix validates exact Arrow integer/float types and column uniqueness before conversion, refuses required-column nulls, and verifies the actual loaded schema again. Separate regressions cover IDs, asset IDs, labels, narrowed sensor/time fields, duplicate columns and legitimate estimator overrides. The pre-fix review suite had 11 failing cases; all 16 review regressions now pass. This illustrates why an independent reproduction matters even after lifecycle and concurrency tests are green.
