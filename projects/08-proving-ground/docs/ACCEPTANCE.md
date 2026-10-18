# Acceptance and independent evidence

The project's mandatory tests have no skips or expected failures. Run all of them using the installed project environment:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked pytest -q --cov=pp_proving_ground --cov-branch
```

| Gate | Mechanism and tests |
| --- | --- |
| PG-01 | `tests/acceptance/test_lifecycle.py`: complete seeded lifecycle; separate repeated fits for prior, logistic and tree reproduce held-out predictions at absolute tolerance `1e-12`. `test_loaded_pipeline_reproduces_predictions` verifies the persisted fitted pipeline. Parquet metadata/dataset identity and frozen split reproducibility are checked independently. |
| PG-02 | `tests/unit/test_contracts.py`: deliberately overlapping rows, asset-policy overlap, unavailable feature times, label-derived declared features, future availability offsets, wrong manifest identity/version, purge and embargo violations. `tests/property/test_invariants.py` generates seed/policy combinations and checks each membership against raw times/asset sets. |
| PG-03 | `test_train_only_preprocessing_independent_median` plants huge held-out values and computes permitted medians independently from raw training indices. `test_test_outcomes_do_not_change_training_validation_or_policy` flips final-test outcomes and proves validation/training/policy decisions stay unchanged. Test-role reports fail the gate, and the staged CLI refuses prepromotion final-test evaluation. |
| PG-04 | The real lifecycle rejects a prior candidate and promotes a validation-qualified fitted model. Missing, nonfinite, undefined and insufficient metrics fail closed; an actual one-class validation report has undefined PR/ROC metrics. Binding tests reject another candidate/data/split/report. Decisions retain candidate, metrics report, gate policy and expected generation. |
| PG-05 | `tests/integration/test_registry_and_serving.py`: two synchronized SQLite promotions produce one winner and one audited stale rejection. A paused earlier model load finishes after a newer deployment and cannot replace it. `test_registry_state_machine.py` compares generated promote/rollback/stale/failing-metric histories against an independent integer reference and restarts the real SQLite registry between observations. |
| PG-06 | ASGI and real loopback HTTP predictions match offline fitted-pipeline predictions. `tests/integration/test_artifacts.py` refuses corrupt bytes/manifests, incompatible formats/libraries, symlinks, malformed skops, unsupported structures and custom types with otherwise valid checksums. |
| PG-07 | Explicit barriers pause prediction after snapshot capture, swap the deployed model, and prove that both the returned probabilities and version/artifact/applied-generation still belong to the captured pipeline. Failed candidate loading retains the previous snapshot and marks readiness pending/failed; rollback creates a newer generation referring to the earlier model. First-load failure yields unavailable predictions. |
| PG-08 | Descriptive monitoring tests inject shifted means, missing values and schema changes. A child process abruptly exits after writing a serialized stage; recovery removes only unpublished stages and preserves valid artifacts. Injected interrupted publication and separately recorded run attempts exercise restart behavior. |

## Coverage scope

The domain core is `data_contracts/schema.py`, `splits/manifest.py`, `experiments/identity.py`, `training/pipeline.py`, `evaluation/metrics.py`, `artifacts/store.py`, `registry/sqlite.py`, `serving/service.py` and `monitoring/drift.py`. It excludes CLI plumbing, HTTP routing and report/provenance formatting when interpreting the branch target. Overall package coverage is also reported rather than concealing wrapper coverage.

## Accepted verification

PG-01–PG-08 passed on the required local platform. Both clean-source compatibility suites passed **103 tests** with normal lint/type/build/package checks, actual demos and CI workloads: [Python 3.13.16](../../../docs/evidence/final/python313/proving-ground-3.13.16.json) and [Python 3.14.8](../../../docs/evidence/final/python314/proving-ground-3.14.8.json). [Independent review](../../../docs/evidence/INDEPENDENT_REVIEW.md) additionally closed **58 checks**, including the separately reproduced physical-Parquet coercion, parameter-override and split-policy defects.

The full standard gate also **passed** at clean commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030` with source unchanged: [raw benchmark](../../../docs/evidence/final/standard/proving-ground-3.14.8-benchmark-benchmark.json) and [execution/provenance wrapper](../../../docs/evidence/final/standard/proving-ground-3.14.8.json). Its actual workload generated 250,000 rows across 500 assets and 40 sensors; all 147,000 permitted training observations were fitted, with 46,000 validation and 49,000 final-test observations and 8,000 purged/embargoed rows. It ran all three model families, 100 asset-cluster bootstrap repetitions, five measured inference batches after warmup and five real registry/load/snapshot transitions. Corruption refusal, prior rejection, offline parity at absolute tolerance 1e-12 and rollback generation 8 all passed. [BENCHMARKS](BENCHMARKS.md) reports exact quality, calibration, slice counts, runtime and uncertainty with their limits.

The wrapper project digest is `eeea22a62454d2e7ae28c739abf45172110edab8f5ebcc24d5037d1a94e39552` and the raw runner digest is `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6`; each uses its own explicit source-input scope. Both retain the same source commit, lock digest `48ddce6dd70acac05a8094cf70e3d40ee7feb534591e49776292ef00436a508f`, clean flag and unchanged-input checks. This does not imply that remote CI ran or that every other portfolio project passed.

[Historical development captures](../artifacts/ci-development-summary.json) retain their original dirty-state provenance and are superseded for current verification by the accepted records above. Transient `/workspace/results/a08-*` paths are development history, not durable final evidence.

Independent authored regressions in `tests/integration/test_review_regressions.py` cover wrong/fractional physical Parquet types, duplicate columns, nonnull integer contracts, valid parameter overrides, NaN/inf split fields, exact integer membership indices and unrelated/future SQLite format refusal. Their pre-fix reproduction and closure are described in [CASE_STUDY](CASE_STUDY.md). [AGENT_STATUS](AGENT_STATUS.md) records completed local gates and the operational boundaries. Generated-equipment metrics and clustered uncertainty do not establish real-equipment utility or guarantee unseen-fleet behavior.
