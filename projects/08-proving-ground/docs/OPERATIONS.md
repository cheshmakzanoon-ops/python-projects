# Operating Proving Ground

Run from this project directory with uv 0.12.23 and the locked Python 3.14.8
environment. Python 3.13.16 uses a separate environment. No external service,
credential, GPU, or downloaded dataset is required. On a managed machine use
`UV_CACHE_DIR=/workspace/.cache/uv` and
`UV_PYTHON_INSTALL_DIR=/workspace/.python` if the home directory is read-only.

## Generate, train, and approve

Choose a fresh absolute output directory. These fixed-seed commands create one
logistic candidate, inspect its validation results, and explicitly request its
first deployment:

```sh
uv sync --locked --python 3.14.8
uv run --locked python -m pp_proving_ground.cli generate --output /tmp/pg-staged --seed 1729
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli train --output /tmp/pg-staged --estimator logistic --seed 1729
uv run --locked python -m pp_proving_ground.cli inspect --output /tmp/pg-staged
uv run --locked python -m pp_proving_ground.cli promote --output /tmp/pg-staged --version 1 --expected-generation 0
uv run --locked python -m pp_proving_ground.cli evaluate --output /tmp/pg-staged --version 1 --role test
uv run --locked python -m pp_proving_ground.cli model-card --output /tmp/pg-staged
```

For other runs, use actual version and generation numbers returned by `inspect`.
Review `promotion_failures` before promotion. The prior is deliberately weak and
normally fails. Test evidence is descriptive after selection; the staged CLI
refuses it before that candidate has been promoted. Entity holdout requires
`generate --split-policy entity` and asks a different scientific question.

`demo --output /tmp/pg-demo --seed 1729` exercises all three families, rejected
prior evidence, accepted candidates, offline/served parity, corruption refusal,
and audited rollback. It is a convenient smoke workflow; the explicit stages
above expose the operator decisions.

## Serve the applied snapshot

```sh
uv run --locked python -m pp_proving_ground.cli serve --output /tmp/pg-staged --port 8108
```

| Endpoint | Meaning |
| --- | --- |
| `GET /health` | Process liveness; does not require a loaded model. |
| `GET /ready` | 200 only when the requested generation is applied; otherwise 503. |
| `GET /deployment` | Requested deployment and current serving state. |
| `GET /models?after=0&limit=20` | Registered model identities. |
| `POST /refresh` | Retry the current requested generation; concurrent retries share a load. |
| `POST /predict` | 1–1000 exact-schema records; response binds probabilities to one actual snapshot. |

For the default twelve-sensor data:

```sh
curl --fail-with-body http://127.0.0.1:8108/predict \
  --header 'Content-Type: application/json' \
  --data '{"records":[{"sensor_00":0.1,"sensor_01":-0.2,"sensor_02":0,"sensor_03":null,"sensor_04":0,"sensor_05":0,"sensor_06":0,"sensor_07":0,"sensor_08":0,"sensor_09":0,"sensor_10":0,"sensor_11":0}]}'
```

All sensor keys are required; null is the explicit missing value. Booleans,
strings, NaN, and infinity are refused. Oversize bodies return 413, invalid
records 422, and missing loaded snapshots 503. Validation responses identify
fields and reasons without reflecting request values. CLI `predict --input
/absolute/records.json --output /tmp/pg-staged` accepts a JSON list of records
without the HTTP wrapper and returns the same snapshot metadata.

The watcher attempts each new requested generation once. An explicit refresh
retries a failed load. A previous valid snapshot remains available with its old
model/version/generation until a newer load succeeds. Inspect readiness as well
as prediction metadata: successful old predictions do not mean the new request
was applied. Shutdown prevents late loaders from publishing; a captured
prediction may finish. Create a fresh `ServingProcess` for another API lifespan.
The CLI binds loopback and supplies no authentication.

## Promotion, stale decisions, and rollback

Promotion and rollback require the generation actually observed before the
operator's decision. A stale comparison is audited and rejected. Inspect the
winner and decide again; do not blindly retry. Rollback still checks the frozen
policy and artifact and requires a previously deployed target. It creates a
new generation instead of deleting history.

For example, after model 1 and model 2 have both been deployed and generation 2
is current:

```sh
uv run --locked python -m pp_proving_ground.cli rollback --output /tmp/pg-staged --version 1 --expected-generation 2
```

If a command exits after SQLite COMMIT but before returning, the transition can
be durable despite the lost response. `inspect` resolves that uncertainty. The
same deployment and audit decision commit atomically; a rejection commits an
audit decision without creating a deployment.

## Upgrade legacy evaluation evidence

Old schema-v1 reports could misattribute another pipeline's statistics to a
published model. New promotion requires schema 2 and frozen policy
`validation-artifact-v2`. Numeric thresholds are unchanged. The default writable
open refuses old policies before changing them. Explicit legacy-policy opens
are also read-only. Never edit the policy hash, rewrite an old report's version,
or relabel its statistics to bypass this boundary.

Stop training/promotions and retain a cold backup first. Inspect historical
state, then reevaluate into a fresh external registry:

```sh
uv run --locked python -m pp_proving_ground.cli inspect --output /tmp/pg-staged
uv run --locked python -m pp_proving_ground.cli reevaluate-registry \
  --output /tmp/pg-staged --destination /tmp/pg-reassessed/registry.sqlite3
uv run --locked python -m pp_proving_ground.cli inspect \
  --output /tmp/pg-staged --registry /tmp/pg-reassessed/registry.sqlite3
```

The command writes `/tmp/pg-reassessed/registry.sqlite3.reevaluation.json` with
source/target policy identities, old/new model and report mapping, gate failures,
and artifact errors. It leaves the target at generation 0 with no deployment.
`completed` means all artifacts were scored, not that they passed quality gates.
Unreadable, corrupt, or incompatible candidates produce `partial` and exit 1;
successfully scored candidates remain visible. Existing target/report paths are
refused. An interrupted reevaluation can leave a partial new registry; retain it
for diagnosis and choose a new destination for a complete retry.

Default current and legacy policies are recognized automatically for audit.
For an originally customized policy, supply its exact original `GatePolicy`
JSON through `--source-policy /absolute/original-policy.json`. Its digest must
match the frozen source. Recover that configuration from the original approved
experiment; do not guess new thresholds to make an old hash match. Reevaluation
uses the current default policy, frozen before scoring, and the output's exact
dataset/split. A candidate trained against another dataset is reported as an
error, requiring its original inputs for separate reevaluation.

Every registry-dependent stage accepts `--registry`: train, evaluate, inspect,
model-card, promote, rollback, predict, and serve. This permits direct adoption
without moving or overwriting the legacy database. If reevaluated candidates
fail, train a replacement into the new registry and review its actual output:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run --locked python -m pp_proving_ground.cli train --output /tmp/pg-staged \
  --registry /tmp/pg-reassessed/registry.sqlite3 --estimator logistic --seed 1729
# Substitute the actual qualified target version printed by train:
uv run --locked python -m pp_proving_ground.cli promote --output /tmp/pg-staged \
  --registry /tmp/pg-reassessed/registry.sqlite3 --version 2 --expected-generation 0
uv run --locked python -m pp_proving_ground.cli serve --output /tmp/pg-staged \
  --registry /tmp/pg-reassessed/registry.sqlite3 --port 8108
```

**The external registry still uses `/tmp/pg-staged/models`, and evaluation also
needs that output's dataset and split.** The target database alone is not an
independent migration or backup. Preserve the complete output plus every
external registry/report. Do not run `clean-demo` on an output while any external
registry or serving process depends on its model store. Historical registry
and audit remain in their original file; adding a new fit can add immutable
models and attempt records to the shared output without changing old decisions.

Python audit access is `Registry.open_read_only(path, store, original_policy)`.
It can read models, reports, current deployment, and audit. Register/promote and
SQL writes on its connections are refused. Serving requires the current policy even when passed a read-only registry.
Promotion also requires a writable current registry; audit access does not regain legacy deployment authority.

## Diagnose a failed boundary

| Observation | Response |
| --- | --- |
| Frozen-policy mismatch | Use read-only inspection and reevaluation above; retain the old registry. |
| Artifact checksum mismatch | Preserve the rejected bytes; restore exact trusted backup bytes or choose another verified candidate. Do not rewrite a checksum. |
| Unsupported persistence-library versions | Recreate the project's locked environment; arbitrary cross-version model loading is refused. |
| Unreviewed types or pipeline/preprocessing mismatch | Keep the artifact for diagnosis and train a reviewed candidate. Do not trust the serializer's unknown-class list automatically. |
| Pending readiness or `load_error` | Compare requested/applied generations and verify the requested artifact; `/refresh` retries after an exact repair. |
| Required metric undefined or insufficient samples | Inspect validation counts and class balance. One-class discrimination cannot authorize deployment. |
| Drift/schema difference | `drift --output ... --incoming /absolute/input.parquet` describes changes; it does not demonstrate accuracy loss without labels. |
| Interrupted serialization | Under exclusive store ownership, `ArtifactStore(...).recover_staging()` removes only unpublished stages. Do not run it beside an active publisher. |

A loaded pipeline stays usable if its immutable on-disk archive later becomes
unreadable; a subsequent load must fail verification. Restore original content
from trusted backup or select a different verified model. A serving response's
metadata always describes its captured model, not whichever registry request was
read afterward.

## Backup, restore, and cleanup

For the simplest backup, stop writers and serving, close SQLite connections, and
copy the complete owned output and every selected external registry/report. Keep
original dataset, split, attempt records, immutable models, report identities,
and deployment history together. Preserve the dependency between each registry
and its configured model-store root.

An online backup requires SQLite's backup API to create a database snapshot,
then copying every artifact referenced by **that snapshot**. Copying the database
file alone while WAL writers run is not a backup protocol. Published artifacts
are immutable and the product has no automatic published-artifact garbage
collection, so they remain available while copying. Dataset/split/run records
also need an explicit consistent capture policy; a registry backup alone does
not include them.

Restore to an isolated directory. Open the restored registry read-only, verify
all referenced artifacts, then use current-contract serving and a known
prediction/readiness check. Legacy evidence requires reevaluation before new
serving. A copied ownership marker intentionally retains its original path, so
`clean-demo` cannot accidentally delete the copied backup.

`clean-demo --output /tmp/pg-staged` recursively removes an owned output with
recognized entries. It rejects symlink roots, marker mismatches, and unexpected
files. It cannot discover arbitrary external registries pointing at that store;
resolve those dependencies before deletion. External registry paths are not
removed by this command.

## Validate and measure

From the repository root, run `python scripts/portfolio.py check proving-ground`.
It checks formatting, lint, strict types, complete tests, fresh distributions,
and an installed-wheel demo. Repeat sequentially with `PORTFOLIO_PYTHON=3.13`
for the isolated compatibility environment.

The bounded bootstrap workload and historical 250,000-row lifecycle are separate
scopes in [BENCHMARKS.md](BENCHMARKS.md). Full workloads should run alone from an
immutable source export. Hashes, model probes, and local SQLite crash schedules
do not establish arbitrary-code safety, remote fleet coordination, real-data
utility, or exhaustive hardware power-loss durability.
