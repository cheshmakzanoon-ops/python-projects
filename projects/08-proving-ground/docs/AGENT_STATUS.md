# A08 Proving Ground: complete local verification

## Code review addendum — 2026-10-18

The current working-tree review closes two confirmed validation gaps:

- Promotion gates accepted impossible finite metrics, fractional sample counts and
  class balance inconsistent with the declared counts. Nonnumeric metrics raised an
  exception. Gates now reject these reports with explicit reasons; a registry regression
  verifies that rejection leaves the deployment unchanged and records an audit decision.
- Shared inference returned unchecked model probabilities and treated unsupported class
  labels as an all-zero prediction. It now validates binary classes, matrix shape,
  finite probabilities in [0, 1], and row normalization at absolute tolerance 1e-12.
  Both offline inference and serving use this boundary. Real supported sklearn artifacts
  with malformed state fail the serving load probe and retain the previous snapshot.

Fourteen regression cases were added; all twelve initial cases reproduced failures before
the fixes. Full suites pass on Python 3.13.16 (**117 passed in 7.23 s**) and 3.14.8
(**117 passed in 9.17 s**), including leakage/split checks, artifact corruption and trust,
promotion races, rollback, serving swaps, and real loopback HTTP predictions. Ruff
formatting/lint and strict mypy pass on both interpreters; wheel and sdist build pass.
Commands: `python -m pytest -q --tb=short`, `ruff format --check .`, `ruff check .`,
`mypy src`, and `uv build --out-dir /workspace/python-projects/.local/review-builds/proving-ground`.
OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS were all 1 for numerical tests.

One upstream Starlette/httpx test-client deprecation warning remains. Heavy benchmarks
were not rerun. The historical evidence below describes its original source revisions
and does not verify these working-tree changes. No dependency, lockfile or shared tracked
files changed. Writes stop at coordinator handoff.

## Previous accepted verification

## Accepted state

PG-01–PG-08, both interpreter compatibility checks, independent review closure and the full standard workload passed. The coordinator accepted the standard run from clean detached source commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030` with source unchanged afterward. No A08 implementation, acceptance or standard-benchmark gate remains open. Repository commit/push and remote CI status are separate coordinator-owned facts; this document does not infer them from local success.

Only this project's documentation was updated after the accepted run. Source, tests, dependencies and benchmark inputs remain frozen. Default Python is 3.14.8; required compatibility includes 3.13.16. Linux x86_64 is the verified platform.

## Durable verification evidence

| Verification | Result | Accepted evidence |
| --- | --- | --- |
| Python 3.13.16 | 103 tests, lint, strict typing, build/package check, demo and CI benchmark passed | [Compatibility wrapper](../../../docs/evidence/final/python313/proving-ground-3.13.16.json) |
| Python 3.14.8 | 103 tests, lint, strict typing, build/package check, demo and CI benchmark passed | [Default-interpreter wrapper](../../../docs/evidence/final/python314/proving-ground-3.14.8.json) |
| Independent review | 58 closure checks passed, including the separately reproduced Parquet identity/parameter/split defects | [Independent review](../../../docs/evidence/INDEPENDENT_REVIEW.md) |
| Full standard workload | 250,000 rows, 40 sensors, 500 assets; three actual fitted model families, full permitted training, 100 asset bootstraps | [Raw measurements](../../../docs/evidence/final/standard/proving-ground-3.14.8-benchmark-benchmark.json), [execution/provenance wrapper](../../../docs/evidence/final/standard/proving-ground-3.14.8.json) |

The compatibility runs name clean source `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`; the standard run names clean source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. Both wrappers identify the same project input digest `eeea22a62454d2e7ae28c739abf45172110edab8f5ebcc24d5037d1a94e39552`. Exact source-input lists, relevant root-input hashes, command arguments, exit codes and unchanged-source checks are retained in those wrappers.

Standard raw runner digest: `2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6`. Lock digest: `48ddce6dd70acac05a8094cf70e3d40ee7feb534591e49776292ef00436a508f`. Raw and wrapper project/root hashes cover different explicit input lists, so their digest strings are not interchangeable. The accepted wrapper's project hash includes README and its root hash covers the broader portfolio contract; the raw runner records its narrower documented local scope.

Toolchain: uv 0.12.23; numpy 2.5.4, scikit-learn 1.9.1, pyarrow 26.0.0, skops 0.16.0, FastAPI 0.143.3 and uvicorn 0.54.0 from the committed lock. All standard numerical thread variables were 1. The run used an Intel Xeon Platinum 8573C and a 34,359,738,368-byte cgroup memory limit. This is local synthetic-workload evidence, not deployed production usage.

## Full workload result

Seed 1729 generated all 250,000 observations. The frozen six-hour-horizon/two-hour-embargo temporal split used **147,000 training, 46,000 validation and 49,000 test rows**, excluding 8,000 rows under purge/embargo rules. All 147,000 permitted training rows were fitted; no training downsampling was used. Dataset identity is `7ab7b11b08606ab8e5d8b3c84368bf6ef000dee43486bdf3e7e2f92cc678cad7` and split identity is `84f03e97bb4a9d7bd07201f9578275dc459bcabe212069e0df15d71d38d5c7a6`.

The selected logistic model had validation PR-AUC **0.862534**, ROC-AUC **0.928634** and Brier **0.097157**. Its 100-repetition asset-cluster PR-AUC percentile interval was [0.856462, 0.871209]. The descriptive postselection test report used 49,000 observations and gave PR-AUC **0.858205**, ROC-AUC **0.930257** and Brier **0.093795**. Test judgments did not select the candidate or promotion thresholds.

Measured lifecycle time was **23.953577 s**; peak RSS **870,920,192 bytes**. Five measured 1,000-row inference batches, after one warmup, had median **2.306749 ms** and interpolated sample p95 **2.744622 ms**. Five registry/verified-load/snapshot transitions took **10.310927–16.033122 ms**. These are five local repetitions, not a stable production tail-latency estimate or five training trials.

The prior was rejected for PR-AUC, ROC-AUC and Brier policy failures. Corruption refusal, offline/served parity at absolute tolerance 1e-12, unchanged source and rollback generation 8 all passed. Final readiness reported selected logistic model version 2 with requested and applied generation 8 and no load error. Complete fit times, model sizes, calibration bins, sample-counted slices and every promotion/rollback decision are in the raw report.

## Acceptance and review closure

[ACCEPTANCE](ACCEPTANCE.md) maps PG-01–PG-08 to concrete tests. Relevant evidence includes immutable data/split/run identity, independent train-only median checks, altered held-out labels, missing/one-class/nonfinite validation failures, candidate/report binding, real SQLite promotion races, generated histories against an independent integer reference, obsolete load refusal, actual loopback HTTP parity, corruption/custom-type refusal, successful rollback and an inference request forced across a swap. Drift reports remain descriptive; interrupted serialization is checked with an abruptly exited child and selective stage recovery.

Independent review reproduced fractional Parquet IDs/labels silently truncating before hashing, duplicate constructor defaults blocking legitimate overrides and a NaN embargo passing split validation. Exact Arrow types, unique columns, required-column null checks and actual loaded-schema validation now precede conversion; validated sklearn overrides and finite/exact split fields close the other defects. Sixteen authored review regressions plus the independent 58-check closure passed. Canonical identity had already refused NaN, so the former embargo-validation defect is not described as a promotion bypass.

Historical authored-suite coverage was 93.28% statements, 81.15% whole-package branches and 216/250 = 86.40% branches across the explicitly defined domain core. Coverage scope and numerical limits are documented; no required tests were skipped or xfailed. One upstream Starlette/httpx TestClient deprecation warning was recorded. A separate real HTTP integration test checks transport and shutdown.

## Historical captures and operations

[The development capture](../artifacts/ci-development-summary.json), based on `3f2c220333fce195c858fa1f08df21676dd51ff1` with dirty=true, remains historical evidence. Its 5,000-row timings are not the standard result. Earlier `/workspace/results/a08-*` outputs are transient development history; the accepted repository evidence linked above is the durable reference.

`uv sync --locked` restores the default environment; `serve --output OWNED_RUN --port 8108` restarts a local serving process. No background service is required for inspection. Runtime outputs use owned directories outside source; [OPERATIONS](OPERATIONS.md) describes inspect, backup, restore, rollback and safe cleanup. Registry format is application_id 1347430193 / user_version 1; unrelated or unsupported databases are refused.

Limits remain explicit: generated equipment outcomes do not establish utility on real machines, asset-bootstrap intervals do not cover all future-fleet uncertainty, leakage checks verify declared contracts, and drift without labels does not prove accuracy loss. No arbitrary model uploads/plugins, public-service authentication or distributed serving fleet is supplied. Linux is validated; Windows CLI resource import is unsupported. Source license remains an owner decision.
