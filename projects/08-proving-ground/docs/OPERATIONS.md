# Operations

Use a fresh absolute output path outside source. Each task already has an isolated environment; use the existing checkout and do not create a Git worktree. Install with `uv sync --locked --python 3.14.8` (3.13.16 remains a required compatibility path). All commands below run inside this project directory.

## Reproduce and inspect

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_proving_ground.cli demo --output /tmp/pg-demo --seed 1729
uv run --locked python -m pp_proving_ground.cli inspect --output /tmp/pg-demo
uv run --locked python -m pp_proving_ground.cli model-card --output /tmp/pg-demo
uv run --locked python -m pp_proving_ground.cli serve --output /tmp/pg-demo --port 8108
```

`GET /health` checks process liveness. `GET /ready` returns 503 while the requested model has not been successfully applied, including a load error. `GET /models?after=0&limit=20` lists model identities. `POST /predict` accepts `{"records":[{"sensor_00":0.1,...}]}` with every named sensor present, values numeric or null. Predictions include artifact digest, actual loaded model version and applied deployment generation. Send JSON lists of those records to `predict --input /absolute/records.json --output /tmp/pg-demo` for the same fitted pipeline through the CLI.

The server polls requested generation changes and attempts each new generation once. `/refresh` retries the current requested generation, for example after restoring an exact original artifact. Retained old predictions always retain old metadata. Loopback-only unauthenticated operation is intentional; the project does not supply production authentication or public deployment.

## Promote and roll back

Inspect current generation before an operator decision:

```bash
uv run --locked python -m pp_proving_ground.cli promote --output /tmp/pg-demo --version 2 --expected-generation 6
uv run --locked python -m pp_proving_ground.cli rollback --output /tmp/pg-demo --version 2 --expected-generation 7
```

These numbers are examples; use actual registry output. A stale generation fails and is audited. A rollback target must have appeared in accepted deployment history and still pass the frozen policy. All report/candidate/data/split bindings must match. Do not repair a rejection by editing stored reports or changing thresholds after inspecting test outcomes; generate a new explicit experiment and policy/registry instead.

## Diagnose and recover

- `artifact checksum mismatch`: preserve evidence, restore the original immutable bytes from a trusted backup, or deploy a different verified artifact. Never rewrite a manifest checksum to legitimize corruption.
- `unreviewed model types`: the serializer found an unsupported class; do not automatically trust the returned class list. Only the documented types were reviewed. Unsupported estimators need a separate compatibility/security review.
- `unsupported persistence-library versions`: recreate the locked environment. Cross-version model loading is intentionally refused.
- generation comparison failure: inspect the winning deployment, then make a fresh reviewed decision using its actual generation. Do not blindly retry a competing promotion.
- missing/undefined metrics: check validation counts and class balance. One-class validation cannot establish required ROC/PR discrimination.
- schema/drift: `drift --output /tmp/pg-demo --incoming /absolute/new-data.parquet` compares the supplied versioned input against the original dataset. Distribution differences alone do not prove accuracy loss.
- interrupted serialization: unpublished `.stage-*` directories can be reconciled by `ArtifactStore(...).recover_staging()` **only with exclusive store ownership**. Published manifests never reference staging. Retrying `train` creates a new attempt under the same semantic run when inputs are unchanged. Incomplete attempts remain visible as started records without completion records.

## Backup and restore

Stop writers/serving for the simplest backup. Copy the owned output tree including the dataset, exact split, run records, immutable `models/` and registry. If writers remain active, use SQLite's backup API for `registry.sqlite3`, then copy every artifact referenced by that snapshot; a file copy of the database alone is not a concurrent backup protocol. Restore to an isolated directory and preserve hashes. Run `inspect`, verify all referenced artifacts using `ArtifactStore.inspect`, then start serving and check readiness and a known prediction. The original ownership marker intentionally binds cleanup to its original directory; copied backups cannot be deleted through `clean-demo` accidentally.

`clean-demo --output /tmp/pg-demo` removes only a matching owned marker directory with recognized generated entries. Unexpected user files, symlink roots and marker mismatches cause refusal. Deleting runtime model state does not modify source or checked-in sample evidence.

## Validate and benchmark

```bash
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked pytest --cov=pp_proving_ground --cov-branch
uv build
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_proving_ground.cli benchmark --profile ci --output /tmp/pg-ci --seed 1729
```

The standard profile uses 250,000 rows and 40 sensors; acquire the portfolio's exclusive benchmark lease first. Run it from an immutable committed source export with `PP_PROVING_GROUND_SOURCE_ROOT` set to that project directory if using a clean installed wheel. Provenance reads source and Git metadata without mutating Git. Missing source metadata is marked unavailable, never invented.
