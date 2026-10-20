# Proving Ground

Proving Ground makes a tabular ML experiment traceable from input data to the
model actually serving a prediction. It freezes dataset and split identities,
owns immutable dataset buffers, fits preprocessing only on training rows,
evaluates verified persisted candidates against a fixed validation policy, and records conditional promotion and rollback decisions.
The equipment-fault task is synthetic; its predictive results do not establish
utility on real equipment.

The lifecycle code owns leakage checks, experiment identity, artifact
publication, promotion audit, and serving consistency. NumPy and scikit-learn
supply numerical estimators; PyArrow supplies columnar storage. No GPU, external
dataset, API key, or database service is required.

## Run the lifecycle

From `projects/08-proving-ground`, with uv 0.12.23:

```sh
uv sync --locked --python 3.14.8
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli demo --output /tmp/pg-demo --seed 1729
uv run --locked python -m pp_proving_ground.cli inspect --output /tmp/pg-demo
```

Choose a new absolute output directory. The demo generates 5,000 correlated
observations, freezes a purged temporal split, and fits prior, logistic, and tree
models. It rejects the prior, promotes a validation-qualified candidate, compares
batch and served predictions at absolute tolerance `1e-12`, refuses a corrupt
artifact copy, and rolls back through audited deployment generations.

The output includes `report.json`, `split.json`, `model-card.json`, `drift.json`,
immutable model artifacts, run attempts, and the SQLite registry. Reports bind
metrics to the exact artifact, dataset, and split. Experiment records bind source
and lock identities; registry decisions bind the frozen policy. Final-test
reports are computed after selection and cannot authorize promotion. Evaluation
loads the published model itself, so a different in-memory fit cannot supply its
statistics.

## Serve and inspect

```sh
uv run --locked python -m pp_proving_ground.cli serve --output /tmp/pg-demo --port 8108
```

| Endpoint | Contract |
| --- | --- |
| `GET /health` | Process liveness; a live process may have no loaded model. |
| `GET /ready` | 200 when requested and applied generations agree; 503 while pending or failed. |
| `GET /deployment` | Requested generation and actual serving state. |
| `GET /models?after=0&limit=20` | Registered model identities. |
| `POST /predict` | 1–1000 records with exactly the named sensors; finite JSON numbers or explicit null. |
| `POST /refresh` | Retry loading the currently requested generation. |

Prediction responses include probabilities, artifact digest, actual model
version, and applied generation from one captured snapshot. Concurrent refreshes
for one generation share one load. Shutdown is terminal and prevents late load
publication. A failed candidate load keeps the previous snapshot and its original metadata; readiness stays
false until the requested generation is applied. Bodies are limited to 2 MiB.
Booleans, numeric strings, and nonfinite values are rejected. The CLI binds to
loopback. This service has no authentication and should remain on a trusted
local machine.

`promote` and `rollback` require the actual current `--expected-generation`.
A stale comparison is rejected and audited. Rollback creates a new generation
for a previously deployed model; it does not delete history. See the
[runbook](docs/OPERATIONS.md) for staged training, request examples, recovery,
backup, and safe cleanup.

Current promotions require schema-v2 verified-artifact reports. Legacy registries
remain available for read-only audit; `reevaluate-registry` scores their actual
artifacts into a fresh undeployed target. Registry-dependent commands accept
`--registry` to adopt that target while retaining history. The target still
depends on the selected output’s model store; preserve that dependency when
backing up or cleaning outputs. See the
[upgrade procedure](docs/OPERATIONS.md#upgrade-legacy-evaluation-evidence).

## Validate changes

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked pytest
uv build --python 3.14.8
```

Python 3.13.16 is also supported. Use separate environments and run the
interpreter checks sequentially. The [verification record](docs/VERIFICATION.md)
separates current regressions from historical full-workload measurements.

Further reading: [architecture](docs/ARCHITECTURE.md),
[design decisions](docs/DECISIONS.md), [numerical contract](docs/EVALUATION.md),
[acceptance mapping](docs/ACCEPTANCE.md),
[benchmarks](docs/BENCHMARKS.md), [case study](docs/CASE_STUDY.md),
[staged example](examples/README.md), and [provenance](docs/THIRD_PARTY.md).

Leakage guards verify declared data contracts; they do not discover hidden causal
relationships. Artifact hashes establish content integrity, not the safety of
arbitrary models. Only the reviewed built-in pipeline families are supported.
Drift reports describe distribution changes, and the small timing samples do not
establish production capacity. No code license has been selected by the owner.
