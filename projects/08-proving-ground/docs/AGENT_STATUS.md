# A08 Proving Ground: verifying

## Current handoff

Original lifecycle implementation, all PG-01–PG-08 local acceptance scenarios, package locks, operational docs, seeded CI workload and standard workload generator/runner are implemented. No required test is skipped, xfailed or mocked in place of the required boundary. Coordinator independent review, final clean committed-source verification and the serialized standard benchmark are outstanding; this status deliberately does not claim project/global completion.

Owned directory: `projects/08-proving-ground`. No Git mutations or shared-file edits were performed by this worker. All generated datasets/models/databases/wheels/caches are ignored or outside tracked source. Source edits are complete; ready for a stable coordinator handoff.

## Verified local commands and evidence

All commands exited 0 unless noted. Toolchain uv 0.12.23; required compatibility Python 3.13.16; evaluated/default Python 3.14.8; Linux x86_64. Locked scientific versions: numpy 2.5.4, scikit-learn 1.9.1, pyarrow 26.0.0, skops 0.16.0. FastAPI 0.143.3 and uvicorn 0.54.0 supply the HTTP boundary.

- `uv sync --locked --python 3.13.16` and `uv sync --locked --python 3.14.8`: successful exact-lock installs.
- `uv run --locked --python 3.13.16 pytest -q --cov=pp_proving_ground --cov-branch`: **103 passed**, no skips. Coverage JSON `/workspace/results/a08-reviewed313-coverage.json`.
- `uv run --locked --python 3.14.8 pytest -q --cov=pp_proving_ground --cov-branch`: **103 passed**, no skips. Coverage JSON `/workspace/results/a08-reviewed314-coverage.json`.
- Full package: 93.28% statements, 81.15% branches, 90.54% combined coverage. Explicit domain core: **216/250 branches = 86.40%**. Scope is documented in ACCEPTANCE.md; wrappers are not hidden from total reporting.
- `uv run --locked ruff format --check .`, `ruff check .`, `mypy src`: passed; strict mypy checks 24 source modules.
- `uv build`: wheel and sdist built; hatchling built the wheel from the sdist.
- Runtime-only wheel installed to `/workspace/results/a08-wheel314` from exact `uv export --locked --no-dev --no-emit-project` dependency pins. `/workspace/results/a08-wheel314/bin/python -I -m pp_proving_ground.cli demo --output /workspace/results/a08-installed-wheel-demo --seed 1729` ran from `/tmp` with `PP_PROVING_GROUND_SOURCE_ROOT` pointing at this project: passed, selected logistic, model version 2, requested/applied generation 8.
- Built-wheel `benchmark --profile ci --output /workspace/results/a08-reviewed-wheel-ci --seed 1729`: passed. Exact output `/workspace/results/a08-reviewed-wheel-ci/benchmark.json`; small authentic checked-in capture `artifacts/ci-development-summary.json`. All benchmark thread variables were 1.

The tests emit one upstream Starlette deprecation warning about its httpx TestClient adapter. It is recorded, not filtered. A separate real uvicorn/httpx loopback integration test validates the actual transport, body limit and shutdown.

## Acceptance depth

PG-01: deterministic dataset/frozen memberships, prior/logistic/tree, seeded refits and loaded prediction tolerance 1e-12.
PG-02: row/entity overlap, feature availability/future-derived declarations, manifest identity, purge/embargo and invalid schema boundaries.
PG-03: independent training median oracle; flipping test outcomes cannot change training/validation/policy; test reports cannot authorize promotion.
PG-04: rejected prior, passing candidate, missing/nonfinite/undefined/insufficient metrics, one-class validation and candidate/data/split/report binding audit.
PG-05: real SQLite promotion race and generation CAS, paused obsolete load, generated promotion/rollback histories against independent integer-state reference.
PG-06: offline/ASGI/real HTTP parity; checksum/format/version/custom-type/malformed serialization refusal.
PG-07: successful new model then actual older-pipeline rollback, failed load retaining old identity, first-load unavailable and prediction forced across a snapshot swap with exact captured metadata.
PG-08: injected drift/schema changes, interrupted publication and abruptly exited child after stage serialization, selective stage recovery and retried attempts.

See ACCEPTANCE.md for exact test links and ARCHITECTURE.md for persistence/trust boundaries.

## Measurement and source identity

CI: 5,000 rows, 50 assets, 12 features. Logistic validation PR-AUC 0.84207 / ROC-AUC 0.91773 / Brier 0.10967; tree PR-AUC 0.77527. Five 900-row served batches median 1.193 ms; five real rollback transitions 13.10–17.87 ms; peak RSS 225,386,496 bytes. Shared development-container measurements, not production capacity.

Capture source base commit `3f2c220333fce195c858fa1f08df21676dd51ff1`, dirty=true, project digest `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6`, lock digest `48ddce6dd70acac05a8094cf70e3d40ee7feb534591e49776292ef00436a508f`. Final committed evidence must supersede this development capture. No future commit or clean-state claim is invented.

## Remaining coordinator gates and restart

1. Review frozen owned files and commit the coherent implementation.
2. From an immutable export, run all normal checks, clean wheel and CI demo on both required interpreters as appropriate.
3. Under the exclusive heavy-workload lease run `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run --locked python -m pp_proving_ground.cli benchmark --profile standard --output ABSOLUTE_NEW_PATH --seed 1729`: generator/runner consumes all 250,000 rows and 40 sensors. This worker did not run standard without a lease.
4. Add clean committed-source standard measurements to repository evidence; coordinator owns Git/push/remote CI status.

No external credential/service blocker. `uv sync --locked` restores the default 3.14.8 environment. `serve --output OWNED_RUN --port 8108` restarts the local service; all tests/demo workers shut down. No running background service is required for the next step.

Known limits: Linux is the validated platform; Windows CLI resource import is unsupported. No arbitrary model plugins, external model uploads, public-service authentication, distributed serving fleet, causal-leak discovery or demonstrated real-equipment predictive utility. Source license awaits owner selection.


## Independent review closure and freeze

A01 independently reproduced a real identity defect: Parquet row/asset IDs and labels were cast to int64 before schema checks, so fractional values could silently truncate back to original values and match the original dataset digest. Exact Arrow schema/column uniqueness/null-required-column checks now precede conversion, and the loaded table schema is checked again. Regressions preserve original embedded digest metadata while altering physical column types; all are refused. Legitimate tree/logistic hyperparameter overrides formerly duplicated default keyword arguments; sklearn `set_params` now validates and applies overrides after default construction. Nonfinite embargo/boundaries and fractional/bool membership indices fail closed. A NaN embargo had passed split validation/training; canonical identity had already refused NaN, so this is not claimed to have been a promotion bypass.

Sixteen review regressions pass. Full reviewed suites: 103 passed on both 3.13.16 and 3.14.8. Three new test-fixture SQLite ResourceWarnings in the first reviewed 3.14 run were fixed using explicit connection closure; the targeted 16-test review suite then passed without those warnings, and the final full 3.13 run had only the upstream Starlette warning. Strict mypy and rebuild passed after source fixes. The rebuilt runtime-only wheel CI benchmark passed from `/tmp`, requested/applied generation 8. These results supersede the earlier 87-test development snapshot, whose earlier runtime output paths remain diagnostic history.

Run specifications and attempts explicitly carry format version 1. Registry files have application_id 1347430193 and user_version 1, initialized transactionally; unrelated/unversioned nonempty databases and future versions are refused. Early unversioned development registries are intentionally unsupported; use a fresh owned demo path. Serialization expanded-size checks run before skops type metadata parsing.

The coordinator confirms immutable verification uses an exact detached local clone with `.git`, so normal Git revision/status capture works without an environment override or invented export metadata. Source edits are frozen for coordinator review and commit. Default remains 3.14.8, compatibility floor 3.13.16. Standard250k40 has not been run by this worker; coordinator holds the serial workload lease.
