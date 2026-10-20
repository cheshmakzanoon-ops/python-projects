# Verification record

Proving Ground is tested on Linux x86_64 with standard CPython 3.13.16 and
3.14.8. Each product owns its dependency lock and virtual environment. Numerical
checks use `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`.

## Core lifecycle review — October 20, 2026

The current scope repairs exact artifact evaluation, dataset snapshot ownership,
publication provenance and serviceability, clustered-AP work, report capture,
and serving load/shutdown ownership. A legacy read-only registry also cannot
start serving through the Python API. The new evaluation report is schema 2;
legacy policy is audit-only. Reevaluation retains the source registry and creates
an undeployed target with model/report mapping and explicit failures.

The actual baseline at `39d3a8d4be3e8e2e7de85379790d68f5367d6825` accepted
and served a prior model using another fitted model's passing statistics. The
[historical fixture](../tests/fixtures/README.md) preserves its original bytes,
manifest, SQL history, and checksums. An additional baseline process exercise
observed eight deserializations for eight same-generation calls, late load
publication after ASGI shutdown, and a returned registration identity differing
from the stored report after a coordinated caller update. Seven dataset alias
cases and three publication-provenance cases failed before correction.

Current verification runs the complete suite on each supported interpreter,
sequentially in separate environments. Both include format/lint, strict typing,
fresh sdist/wheel builds, and an installed-wheel demo with cleanup. The current
case count is **195 passed on each interpreter**, with zero failures, errors,
skips, or expected failures. Exact workspace result paths and JUnit hashes are
recorded in the [core review artifact](../artifacts/core-lifecycle-review.json);
historical counts below describe only their named revisions. The only suite warning is upstream Starlette's deprecation of
its current httpx TestClient integration.

Independent numerical evidence includes all 27 ordered three-asset draws for
three tied-score fixtures, exact rational threshold AP, seeded expanded-fleet
percentiles including undefined draws, and bounded deterministic work. The
five-repeat 20,000-row bootstrap comparison matches baseline endpoints exactly
while eliminating individual-asset rescans and duplicate-row expansion. It is
not a rerun of the historical 250,000-row lifecycle.

SQLite tests abruptly exit real child writers after audit insertion, after
deployment insertion, and after COMMIT. Accepted audit/deployment state remains
atomic; rejected decisions never create deployment. Separate controlled threads
check snapshot capture during caller updates, one load across eight refresh
calls, explicit retry, stale-generation completion, waiter release on close,
and a request finishing after its process closes.

A read-only peer independently checked ten cluster multiplicity combinations
against expanded scikit-learn AP; exact seeded bootstrap quantiles; persisted
prior evaluation; simultaneous conditional promotions and rejection audit; a
child killed after real deployment insertion before COMMIT; coalescing and
terminal close; dataset aliases/strides; legacy byte preservation/reassessment;
and explicit-registry train/promote/serve adoption using actual TestClient
readiness. No further concrete defect was found in that scope. Peer probes were
isolated and did not replace the project's full suite.

Limits remain explicit: the interval is conditional on both classes, gates do
not require a minimum independent-asset count, local report submission is trusted,
loaders cannot be forcibly cancelled, and full hardware power loss or a remote
serving fleet is outside these checks. The working-tree evidence does not claim
an immutable final-commit certificate. No dependencies or lockfile were changed.

## Historical artifact and serving review — October 20, 2026

Artifact publication now synchronizes the staged directory after synchronizing
its model and manifest files and before renaming the directory into the
content-addressed store. The parent store directory is synchronized after rename.
A failed stage synchronization leaves existing artifacts intact and removes the
unpublished stage. Regression tests observe the ordering and inject an I/O
failure at that boundary.

Checksums alone no longer suffice for structurally invalid manifests. Version 1
must be an integer, identity fields must be lowercase SHA-256 digests, and feature
names must be a nonempty array of unique nonempty strings. Artifact members must
be regular files. The loader enforces exact pipeline step order and names,
reviewed preprocessing configuration, and agreement between fitted feature count
and the declared sensor schema.

Record inference rejects booleans, numeric strings, and nonfinite values instead
of silently coercing them. The same boundary applies to the CLI and HTTP API;
JSON null remains the explicit missing-value representation. HTTP validation
errors return locations, explanations, and error types without echoing request
values. This also avoids response-serialization failures for rejected NaN or
infinity tokens. A public ASGI middleware bounds streamed request bodies before
endpoint dispatch, replacing writes to a private request attribute.

Both interpreter checks passed in the review workspace:

| Interpreter | Results |
| --- | --- |
| CPython 3.14.8 | 155 tests, format/lint, strict typing, sdist/wheel build, runtime-only installed-wheel demo and cleanup. |
| CPython 3.13.16 | The same checks and 155 tests in a separate virtual environment. |

The commands were `python scripts/portfolio.py setup proving-ground` and
`python scripts/portfolio.py check proving-ground`, from the repository root
with `PORTFOLIO_PYTHON` set explicitly. The 3.13 environment was
`.local/venvs/proving-ground-3.13.16`; the runs were sequential. No tests were
skipped or marked as expected failures. The existing upstream Starlette/httpx
TestClient deprecation warning remains; production serving does not use it.

The 35 new cases cover artifact and record boundaries plus streamed body
handling. Running the integration cases against the original artifact/service/API
implementation at `da094934b37a80e03b644ec4be8aa8e697da4c49` produced **25
failures and two passes**. Two special-file cases were excluded from that
before-fix run because the old implementation could block when opening a FIFO.
All new cases pass against the corrected code. No dependencies or lockfile were
changed. The full 250,000-row historical benchmark below was not repeated.

## Earlier correctness review — October 18, 2026

An earlier review closed validation gaps in promotion metrics and inference
probabilities. Impossible metric ranges, fractional counts, inconsistent class
balance, unsupported class labels, malformed probability matrices, and nonfinite
probabilities now fail closed. Supported sklearn artifacts with malformed state
fail the serving load probe while preserving the previous snapshot.

That revision passed **117 tests on each supported interpreter**, plus lint,
typing, and package builds. It added fourteen regression cases; the initial
twelve reproduced failures before correction. One upstream Starlette/httpx
TestClient deprecation warning was recorded. Those results describe that earlier
source, before the current artifact and request changes.

## Historical compatibility and workloads

| Verification | Scope and evidence |
| --- | --- |
| Python 3.13.16 | 103 tests, locked install, lint, strict types, builds, installed-wheel demo, and CI workload: [compatibility wrapper](../../../docs/evidence/final/python313/proving-ground-3.13.16.json). |
| Python 3.14.8 | The same checks on the default interpreter: [compatibility wrapper](../../../docs/evidence/final/python314/proving-ground-3.14.8.json). |
| Independent review | 58 closure checks, including Parquet type/identity and split-policy regressions: [review](../../../docs/evidence/INDEPENDENT_REVIEW.md). |
| Standard workload | 250,000 rows, 40 sensors, 500 assets, all three fitted model families, 100 asset bootstraps: [raw measurements](../../../docs/evidence/final/standard/proving-ground-3.14.8-benchmark-benchmark.json) and [execution wrapper](../../../docs/evidence/final/standard/proving-ground-3.14.8.json). |

Compatibility wrappers identify clean source
`7114e39c7e9e8af177e84fe8cd990fe5a09bde63`; the standard wrapper identifies
`59443e2bcdfc6a1dd81f8334c108474eef2d3030`. Their declared project digest is
`eeea22a62454d2e7ae28c739abf45172110edab8f5ebcc24d5037d1a94e39552`.
The raw standard runner uses a narrower input list and digest
`2000f7eb808d0229d9db549fe3683efbb9ced676a49ee8eab7310e66cba01ab6`.
Compare each digest only against its recorded input scope. The lock digest was
`48ddce6dd70acac05a8094cf70e3d40ee7feb534591e49776292ef00436a508f`.

The full temporal split retained 147,000 training, 46,000 validation, and 49,000
test rows, excluding 8,000 under purge/embargo rules. Every permitted training row
was fitted. Dataset identity was
`7ab7b11b08606ab8e5d8b3c84368bf6ef000dee43486bdf3e7e2f92cc678cad7`;
split identity was
`84f03e97bb4a9d7bd07201f9578275dc459bcabe212069e0df15d71d38d5c7a6`.
The selected logistic model's validation PR-AUC/ROC-AUC/Brier were
0.862534/0.928634/0.097157. Its descriptive postselection test values were
0.858205/0.930257/0.093795. The validation asset-bootstrap PR-AUC interval was
[0.856462, 0.871209]. These results concern the generated fleet.

The measured lifecycle took 23.953577 s with peak RSS 870,920,192 bytes. Five
1,000-row inference measurements after warmup had median 2.306749 ms and sample
p95 2.744622 ms. Five registry/load/snapshot transitions took
10.310927–16.033122 ms. This is a small local timing sample, not production tail
latency or repeated training trials. The prior was rejected, corruption was
refused, numerical parity met absolute tolerance `1e-12`, and requested/applied
generation 8 agreed. [BENCHMARKS.md](BENCHMARKS.md) retains machine conditions,
model timings, calibration, slice counts, limitations, and raw provenance.

Historical coverage was 93.28% statements, 81.15% whole-package branches, and
216/250 = 86.40% branches within the declared domain core. It is not current
coverage. The [development capture](../artifacts/ci-development-summary.json)
retains its original dirty-source status and 5,000-row scope rather than being
substituted for the standard workload.

## Operating boundaries

No external service, credential, GPU, or arbitrary-model plugin is needed.
Trusted local registry/report submission is assumed. The loopback HTTP service
has no authentication and is not a public deployment. Hashes and skops type
review are not an arbitrary-code sandbox. Dataset leakage guards verify declared
contracts, and drift without labels does not establish accuracy loss. Local
POSIX synchronization assumptions do not prove every hardware power-loss case.
Source licensing remains an owner decision.
