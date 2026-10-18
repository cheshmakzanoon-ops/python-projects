# Status: complete — final standard and compatibility verified

A06 PyTrace implements the original CFG/worklist/lattice engine, import aliases and lexical shadowing, contextual shell/SQL taint and async blocking rules, bounded parser subprocess, dependency invalidation, official OASIS SARIF, conservative LibCST transforms and recoverable selected-file apply. Work is contained in projects/06-pytrace; no worker Git mutations.

**PY-01–PY-08:** all local acceptance scenarios implemented and passing. See ACCEPTANCE.md for exact tests. The 50 reviewed expression/context/alias/Unicode fixture variants contain 5,600 source lines and 350 independently declared positives with negative contrasts. No claim of independent real-world accuracy.

The coordinator accepted the immutable standard run at `59443e2bcdfc6a1dd81f8334c108474eef2d3030`: [raw measurements](../../../docs/evidence/final/standard/pytrace-3.14.8-benchmark-benchmark.json), [verification wrapper](../../../docs/evidence/final/standard/pytrace-3.14.8.json). Both required compatibility suites retain 77 passing tests: [Python 3.13.16 evidence](../../../docs/evidence/final/python313/pytrace-3.13.16.json) and [Python 3.14.8 evidence](../../../docs/evidence/final/python314/pytrace-3.14.8.json).

Historical development commands, all exit 0:

- `uv sync --locked --python 3.13.16` and isolated `UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv sync --locked --python 3.14.8`.
- `uv run --locked --python 3.14.8 ruff format --check .`, `ruff check .`, `mypy src`: 24 own source files strict checked. Ruff fixture exclusion preserves authored line labels; acceptance still parses/compiles every fixture.
- `UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv run --locked --python 3.14.8 pytest -q --tb=short`: **77 passed in 13.26 s**.
- `uv run --locked --python 3.13.16 pytest -q --tb=short --cov=pp_pytrace.analysis --cov=pp_pytrace.cfg --cov=pp_pytrace.semantics --cov=pp_pytrace.codemods --cov-branch --cov-report=json:/tmp/pytrace-core-coverage.json`: **77 passed in 14.61 s**. Defined own-code core: **93.10% statements, 88.52% branches (216/244), 91.72% combined**. Frontend/cache/reporting/CLI are tested but not included in that declared core coverage figure.
- `uv build --python 3.14.8`: sdist built; wheel built from that sdist. Exact runtime lock export installed with `uv pip install --require-hashes` in clean `/tmp/pytrace-wheel-venv`; final wheel reinstalled with `--no-deps`; outside-checkout `/tmp` demo passed. Vendored schema, notices and benchmark corpus are included in wheel.
- `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv run --locked --python 3.14.8 python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-ci-source --seed 1729`: passed; all four domain correctness checks true, source digest unchanged. Five cold/five warm measurements in artifacts/ci-benchmark.json. Cold median 3.621 s; warm median 0.137 s; ten dependency invalidations; zero parse failures; precision/recall 1.0 on labeled fixtures only.

Default is now CPython **3.14.8**, with **3.13.16** still required/supported. Coordinator manifest request is recorded in SHARED_CHANGE_REQUESTS.md.

Defects corrected during verification: string-valued suppression text must not suppress diagnostics; nested `str(str("text"))` must finish in one pass while preserving docstring abstention; sources need a stat check plus bounded read against growth races before parsing; rejected oversized files must not be fully read to hash them; tiny invalid parser memory budgets must fail before allocation; a pinned fixture API hash legitimately changed after formatting and was reviewed/repinned. Regression tests cover each.

**Final standard:** passed on CPython 3.14.8, 234 files/250,899 lines including 19 graph lines. One cold measurement was 72.576544 s under the documented cost exception; five warm measurements had median 3.254818 s. Incremental analysis took 1.085980 s and invalidated exactly ten files; cache/clean equivalence and closure checks passed with zero parse failures. Tracemalloc peak was 339,695,450 bytes; analyzer RSS and maximum child RSS were each 960,466,944 bytes. These RSS values are neither summed nor a simultaneous machine peak. Standard precision/recall remain null with zero labeled cases: generated scale does not establish accuracy.

PY-01–PY-08 and the required standard workload now have accepted evidence. Historical dirty development artifacts remain unchanged; the final root reports identify their own clean source commit, input scopes and exact hashes. Remaining algorithmic/platform limits are documented in DECISIONS.md and are not claims of full Python soundness or production security certification. No project acceptance gate remains pending in this handoff. Source writes remain paused; the coordinator owns final repository publication.

## Code review addendum — October 18, 2026

The review added 50 regression cases and corrected concrete defects in analysis and editing:

- Truthy constant shell flags and unresolved `**options` now produce shell findings; parser serialization preserves bytes, complex values and Ellipsis instead of silently replacing them with `None`.
- Ambiguous sanitizer aliases retain taint. Call arguments and method receivers are evaluated once in source order, annotation-only statements preserve existing bindings, and conditional expressions/short-circuit operators join possible name writes.
- Wildcard imports cause codemod abstention because introduced bindings cannot be proved. Noncanonical path aliases are rejected before editing, malformed JSON plan shapes raise controlled errors, and unique replacement temporaries allow recovery after an earlier interrupted write. A bounded temporary basename preserves support for long source filenames.
- Structurally corrupt caches and invalid cached diagnostic fields, unknown rules or enum values rebuild analysis. Source discovery ignores directories named `*.py`, rejects an explicit symlink root and refuses nonregular inputs before opening a FIFO can block.

Validation on the reviewed working tree used `UV_CACHE_DIR=/workspace/.cache/uv UV_PYTHON_INSTALL_DIR=/workspace/.python UV_LINK_MODE=copy`:

- Default CPython 3.14.8: `uv run --locked pytest -q` — **127 passed in 16.71 s**; `ruff format --check .`, `ruff check .` and `mypy src` passed (24 source files).
- Isolated CPython 3.13.16: `UV_PROJECT_ENVIRONMENT=/workspace/python-projects/.local/review-venvs/pytrace-3.13 uv run --locked --python 3.13.16 pytest -q` — **127 passed in 16.99 s**; strict mypy passed. These final compatibility suites ran concurrently in separate virtual environments.
- `uv build --out-dir /workspace/python-projects/.local/review-artifacts/pytrace-dist` built the sdist and wheel; project diff whitespace validation passed.

The existing acceptance suite includes the 50-file labeled corpus, SARIF validation, CLI demo, apply/recovery and incremental-cache equivalence. No standard or heavy benchmark was rerun; the measurements above this addendum remain historical evidence for their stated source commit. The documented intraprocedural, hostile-filesystem and power-loss limitations remain. No root/shared files, dependency manifests, lockfiles or Git metadata were mutated by this project review. Writes are paused for coordinator handoff.
