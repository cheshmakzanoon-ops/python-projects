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

Local development evidence lives outside tracked source under `/workspace/results/a08-*`; concise actual captures belong in [artifacts](../artifacts). [AGENT_STATUS](AGENT_STATUS.md) distinguishes local checks from the coordinator's immutable committed-source verification and full standard workload. A passing own-project test suite is not a claim that remote CI ran or that the entire portfolio passed.


Independent review regressions in `tests/integration/test_review_regressions.py` additionally close physical Parquet type/coercion identity failures, duplicate columns, nonnull integer contracts, valid parameter overrides, NaN/inf split policy values, exact membership index types, and unrelated/future SQLite format refusal. The independent pre-fix reproduction and exact closure are recorded in AGENT_STATUS.md.
