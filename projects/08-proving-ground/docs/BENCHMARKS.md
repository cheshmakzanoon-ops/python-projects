# Reproducible measurements

The generator is original and seed-controlled. CI uses 5,000 observations, 50 assets, 12 sensors, a six-hour future fault horizon and two-hour split embargo. Standard uses 250,000 observations, 500 assets and 40 sensors. Both include correlated asset/time effects, imbalanced outcomes, 2.5% missing sensor cells and a controlled 0.4-sigma late-period feature shift. Training uses the full permitted training partition, never a downsample. Prior, logistic and depth-8 tree models use fixed configurations.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli benchmark --profile ci --output /tmp/pg-ci --seed 1729
# Run standard alone under the coordinator's exclusive resource lease:
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli benchmark --profile standard --output /tmp/pg-standard --seed 1729
```

Each `benchmark.json` contains actual source commit/dirty state, explicit project-content digest, relevant root-contract digest, lock digest, interpreter/OS/CPU/cgroup-memory information, seed, dataset digest, parameters, thread environment, one warmup and five timed inference runs. The project digest covers source, tests, examples, benchmarks, pyproject, lock and interpreter pin, excluding reports/artifacts/caches. Relevant root files are AGENTS.md, ruff.toml, portfolio.toml and scripts/portfolio.py. Missing environment metadata is reported as unknown/null; values are never fabricated. Source content is rechecked after the workload.

Measured quantities include full model-fit wall time, model bytes, process peak RSS, validation discrimination/Brier/calibration/slices and asset bootstrap intervals, postselection final-test metrics, five 1,000-row-or-smaller served-inference batches, and five registry-rollback/load/snapshot transition timings. Prediction parity, corruption refusal and actual rollback generations are correctness checks. Transition timings include SQLite commit, verified disk load and snapshot swap; no network latency is folded into them. A single fit per model is reported; the five-repetition comparison applies to inference and registry/serving transition timing, not a claim of five independent training trials.

The CI run establishes an executable small workflow and descriptive baseline. Shared development-container timings include scheduling interference from other small checks; they are not production capacity or isolated hardware claims. Standard workload evidence must be generated serially from the coordinator's committed immutable export. The workload command and result schema are implemented now; [AGENT_STATUS](AGENT_STATUS.md) records whether that full run has actually been performed.

The synthetic outcomes have a known construction favoring linear effects, so logistic strength here does not establish superiority on real equipment. Bootstrap intervals reflect only this generated asset population; tiny slices remain flagged. No byte-identical serialization guarantee is made across saves or platforms.


## Actual reviewed development CI capture

[The recorded capture](../artifacts/ci-development-summary.json) ran the rebuilt runtime-only wheel under Python 3.14.8 from `/tmp`, with source digest `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6` and source base commit `3f2c220333fce195c858fa1f08df21676dd51ff1`, **dirty=true**. This is reviewed development evidence, not a claim of final clean-commit verification. All BLAS/OpenMP settings were 1.

| Model | Fit seconds | Validation PR-AUC | ROC-AUC | Brier | Model bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| prior | 0.01598 | 0.32167 | 0.50000 | 0.21827 | 34,398 |
| logistic | 0.01351 | 0.84207 | 0.91773 | 0.10967 | 40,125 |
| tree | 0.03558 | 0.77527 | 0.85546 | 0.13972 | 55,544 |

Validation had 600 observations and 193 faults. The postselection test had 900 observations and 198 faults; selected logistic PR-AUC 0.83143 / ROC-AUC 0.93624 / Brier 0.08014. Five 900-row inference batches had median 1.193 ms. Five real model rollback/load/swap transitions took 13.10–17.87 ms. Peak RSS was 225,386,496 bytes and elapsed lifecycle 1.052 s. Shared-container timings are descriptive, not isolated hardware or production-capacity claims. Corruption refusal, numerical parity and applied generation 8 were checked by the actual run.
