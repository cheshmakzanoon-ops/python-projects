# Reproducible measurements

## Accepted full standard run

The full standard workload **passed** on clean committed source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`, Python 3.14.8, seed 1729. [Raw benchmark measurements](../../../docs/evidence/final/standard/proving-ground-3.14.8-benchmark-benchmark.json) retain all model/evaluation/transition records. The [execution and provenance wrapper](../../../docs/evidence/final/standard/proving-ground-3.14.8.json) records exact source/root input lists, the standard command, exit code 0 and unchanged source afterward. This accepted run supersedes development-only timing claims.

The original generator produced **250,000 observations, 40 sensors and 500 assets**, including asset/time correlation, class imbalance, 2.5% missing sensor cells and a controlled 0.4-sigma late-period feature shift. The six-hour future label horizon and two-hour embargo froze 147,000 training, 46,000 validation and 49,000 test rows; 8,000 observations were intentionally excluded by purge/embargo. The complete permitted training partition was used for every family, with no downsampling. Temporal boundaries were 299.4 and 399.2 synthetic hours. This split asks future forecasting for an existing fleet and permits asset overlap; the distinct entity-holdout question is tested separately.

Dataset digest: `7ab7b11b08606ab8e5d8b3c84368bf6ef000dee43486bdf3e7e2f92cc678cad7`. Split digest: `84f03e97bb4a9d7bd07201f9578275dc459bcabe212069e0df15d71d38d5c7a6`. Each evaluation binds these identities to its candidate artifact. Gate thresholds were fixed before fitting; candidate selection used validation PR-AUC, and the final test report was computed afterward.

The [compact observation of the actual frozen split](../../../docs/evidence/final/standard/proving-ground-split-observation.json) records counts, exact boundaries, dataset identity and the full split-file checksum. Full row-ID lists are omitted; they can be regenerated from the recorded profile and seed.

| Model | Full fit seconds | Validation PR-AUC | ROC-AUC | Brier | Model bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| prior | 1.329923 | 0.308196 | 0.500000 | 0.216095 | 36,190 |
| logistic | 1.289020 | 0.862534 | 0.928634 | 0.097157 | 42,365 |
| tree | 8.012962 | 0.844356 | 0.919862 | 0.102623 | 87,103 |

All validation metrics used 46,000 observations, including 14,177 faults (30.8196%). The prior failed all three quality gates. Logistic was selected with PR-AUC 0.862534 and an asset-cluster 95% percentile interval [0.856462, 0.871209], from 100 defined bootstrap repetitions across 500 assets. This is descriptive uncertainty for the generated fleet, not a guarantee for unseen real fleets. PR-AUC means sklearn average precision.

Validation's four fixed asset-modulo slices each had 11,500 observations; their logistic PR-AUC ranged 0.849149–0.870028. Missing-sensor and complete-sensor slices had 29,325 and 16,675 observations, with PR-AUC 0.855690 and 0.874187. All six slices exceeded the declared minimum sample count. These differences do not establish causal effects of missingness. Ten calibration bins are retained: for example, the [0.0,0.1) bin held 20,506 observations with mean prediction 0.025551 versus observed rate 0.024627; the [0.9,1.0] bin held 4,766 with 0.961304 versus 0.956358.

The postselection logistic test report used 49,000 observations and 14,248 faults: PR-AUC 0.858205, ROC-AUC 0.930257 and Brier 0.093795. Its 100 asset-bootstrap PR-AUC percentile interval was [0.850582,0.866559]. Final-test judgments were descriptive and could not authorize promotion or choose thresholds.

| Runtime measurement | Actual result |
| --- | ---: |
| Complete lifecycle wall time | 23.953577 s |
| Peak process RSS | 870,920,192 bytes |
| Served inference batch | 1,000 rows |
| Warmup / measured inference runs | 1 / 5 |
| Inference median / sample p95 | 2.306749 / 2.744622 ms |
| Five registry/load/snapshot transitions, min–max | 10.310927–16.033122 ms |
| Transition median | 11.552346 ms |

The five inference measurements were 2.115305, 2.360746, 2.085273, 2.840591 and 2.306749 ms. The five transition measurements included the SQLite generation transition, hash/type/version-verified disk load and atomic serving snapshot swap; they do not include HTTP latency. The sample p95 is interpolated from five measurements and is not a stable production tail estimate. Each family was fitted once; five repetitions apply to inference and transitions, not training.

The run used an Intel Xeon Platinum 8573C, Linux x86_64, a 34,359,738,368-byte cgroup limit and OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1 during a serialized workload run. The lifecycle timer excludes dispatcher overhead; the wrapper separately records 25.698055 s for the whole standard command. These are local synthetic-workload measurements, not a production-capacity claim.

Correctness checks passed: prior rejected, corrupt artifact copy refused, offline/served pipeline parity at absolute tolerance 1e-12, unchanged source, audited rollback generation 8. Final readiness showed requested/applied generation 8, logistic model version 2 and no load error. The raw audit binds every decision to candidate/data/split/evaluation/policy identities and records all real tree/logistic rollback transitions.

## Reproduce and inspect provenance

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli benchmark --profile ci --output /tmp/pg-ci --seed 1729
# Run standard alone alone on an idle machine:
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli benchmark --profile standard --output /tmp/pg-standard --seed 1729
```

CI uses 5,000 rows, 50 assets and 12 sensors. The accepted full standard result above is not inferred from CI. [Python 3.13.16 compatibility evidence](../../../docs/evidence/final/python313/proving-ground-3.13.16.json) and [Python 3.14.8 evidence](../../../docs/evidence/final/python314/proving-ground-3.14.8.json) record clean-source normal checks, demos and CI benchmarks; both suites passed 103 tests. [Independent review](../../../docs/evidence/INDEPENDENT_REVIEW.md) closed 58 additional checks.

The standard wrapper project digest is `eeea22a62454d2e7ae28c739abf45172110edab8f5ebcc24d5037d1a94e39552`; raw runner project digest is `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6`; lock digest is `48ddce6dd70acac05a8094cf70e3d40ee7feb534591e49776292ef00436a508f`. These project hashes use separate declared input scopes; the wrapper also includes README in its explicit source-input manifest. Its broader root-contract manifest likewise differs from the raw runner's narrower historical root-contract scope. Both identify the same clean source commit and confirm unchanged inputs after execution; compare each digest only against its declared input list.

Every result records seed, dataset identity, parameters, actual interpreter/OS/CPU/memory information, thread settings, measurements and correctness checks. Generated reports/artifacts are excluded from source hashing to avoid self-reference. Unknown environment metadata is never fabricated. The synthetic outcome construction favors linear effects: logistic strength here does not establish superiority on real equipment. Asset-bootstrap intervals describe this generated population, drift alone does not demonstrate accuracy loss, and serialization bytes need not repeat across saves or platforms.

## Historical development CI capture

[The recorded capture](../artifacts/ci-development-summary.json) ran the rebuilt runtime-only wheel under Python 3.14.8 from `/tmp`, with source digest `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6` and source base commit `3f2c220333fce195c858fa1f08df21676dd51ff1`, **dirty=true**. This is reviewed development evidence, not a claim of final clean-commit verification. All BLAS/OpenMP settings were 1.

| Model | Fit seconds | Validation PR-AUC | ROC-AUC | Brier | Model bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| prior | 0.01598 | 0.32167 | 0.50000 | 0.21827 | 34,398 |
| logistic | 0.01351 | 0.84207 | 0.91773 | 0.10967 | 40,125 |
| tree | 0.03558 | 0.77527 | 0.85546 | 0.13972 | 55,544 |

Validation had 600 observations and 193 faults. The postselection test had 900 observations and 198 faults; selected logistic PR-AUC 0.83143 / ROC-AUC 0.93624 / Brier 0.08014. Five 900-row inference batches had median 1.193 ms. Five real model rollback/load/swap transitions took 13.10–17.87 ms. Peak RSS was 225,386,496 bytes and elapsed lifecycle 1.052 s. Shared-container timings are descriptive, not isolated hardware or production-capacity claims. Corruption refusal, numerical parity and applied generation 8 were checked by the actual run.
