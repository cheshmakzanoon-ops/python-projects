# Proving Ground

Proving Ground is a local ML lifecycle platform for a synthetic equipment-fault forecasting task. It makes split leakage, experiment identity, validation decisions, artifact trust and serving generations inspectable. Its authored core is the lifecycle contract; NumPy, scikit-learn and PyArrow supply numerical estimators and storage primitives.

```bash
uv sync --locked --python 3.14.8
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli demo --output /tmp/pg-review --seed 1729
```

The real demo generates 5,000 correlated observations, freezes purged temporal splits, trains prior/logistic/tree models, rejects the prior, conditionally deploys a validation-qualified candidate, checks batch/served parity at absolute tolerance `1e-12`, refuses a corrupt artifact copy, rolls back through new audited generations, and writes a model card. It does not need credentials, external datasets or a GPU. Choose an empty output directory; existing runs are preserved.

Inspect `/tmp/pg-review/report.json`, `model-card.json`, `drift.json`, `split.json`, and the SQLite registry. Run `inspect --output /tmp/pg-review` to see models and all accepted/rejected decisions. Trigger a stale-generation refusal using `promote --output /tmp/pg-review --version 2 --expected-generation 0`; the audit records the rejection.

```bash
uv run --locked python -m pp_proving_ground.cli serve --output /tmp/pg-review --port 8108
# In another terminal: curl http://127.0.0.1:8108/ready
```

The service watches requested generations, loads and verifies candidates before swapping a complete snapshot, and returns actual loaded version/artifact/applied-generation on every prediction. `/ready` distinguishes pending/failed loads from liveness. The loopback demo has no authentication and is not intended for public exposure.

Other commands: `generate`, `train`, `evaluate`, `promote`, `rollback`, `predict`, `drift`, `model-card`, `inspect`, `benchmark`, and `clean-demo`. See [the staged example](examples/README.md) and [operations](docs/OPERATIONS.md).

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md): identity boundaries, purging, publication and generation safety.
- [Acceptance map](docs/ACCEPTANCE.md): PG-01–PG-08, independent oracles, adversarial and process tests.
- [Benchmarks](docs/BENCHMARKS.md): seeded CI and 250,000-row/40-feature standard workloads.
- [Case study](docs/CASE_STUDY.md): a real serialization-identity mistake and its regression evidence.
- [Provenance](docs/THIRD_PARTY.md) and [current verification status](docs/AGENT_STATUS.md).

This generated task is a scientific/engineering demonstration, not demonstrated utility on real equipment. Leakage guards verify declared data contracts, not hidden causal relationships. Final-test reports are descriptive and cannot authorize a promotion. No code license has been selected by the repository owner; see provenance before redistribution.
