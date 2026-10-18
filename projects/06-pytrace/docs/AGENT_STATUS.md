# Status: verifying — local gates passed; coordinator standard/review pending

A06 PyTrace implements the original CFG/worklist/lattice engine, import aliases and lexical shadowing, contextual shell/SQL taint and async blocking rules, bounded parser subprocess, dependency invalidation, official OASIS SARIF, conservative LibCST transforms and recoverable selected-file apply. Work is contained in projects/06-pytrace; no worker Git mutations.

**PY-01–PY-08:** all local acceptance scenarios implemented and passing. See ACCEPTANCE.md for exact tests. The 50 reviewed expression/context/alias/Unicode fixture variants contain 5,600 source lines and 350 independently declared positives with negative contrasts. No claim of independent real-world accuracy.

Final development commands, all exit 0:

- `uv sync --locked --python 3.13.16` and isolated `UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv sync --locked --python 3.14.8`.
- `uv run --locked --python 3.14.8 ruff format --check .`, `ruff check .`, `mypy src`: 24 own source files strict checked. Ruff fixture exclusion preserves authored line labels; acceptance still parses/compiles every fixture.
- `UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv run --locked --python 3.14.8 pytest -q --tb=short`: **77 passed in 13.26 s**.
- `uv run --locked --python 3.13.16 pytest -q --tb=short --cov=pp_pytrace.analysis --cov=pp_pytrace.cfg --cov=pp_pytrace.semantics --cov=pp_pytrace.codemods --cov-branch --cov-report=json:/tmp/pytrace-core-coverage.json`: **77 passed in 14.61 s**. Defined own-code core: **93.10% statements, 88.52% branches (216/244), 91.72% combined**. Frontend/cache/reporting/CLI are tested but not included in that declared core coverage figure.
- `uv build --python 3.14.8`: sdist built; wheel built from that sdist. Exact runtime lock export installed with `uv pip install --require-hashes` in clean `/tmp/pytrace-wheel-venv`; final wheel reinstalled with `--no-deps`; outside-checkout `/tmp` demo passed. Vendored schema, notices and benchmark corpus are included in wheel.
- `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 UV_PROJECT_ENVIRONMENT=/tmp/pytrace-venv314 uv run --locked --python 3.14.8 python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-ci-source --seed 1729`: passed; all four domain correctness checks true, source digest unchanged. Five cold/five warm measurements in artifacts/ci-benchmark.json. Cold median 3.621 s; warm median 0.137 s; ten dependency invalidations; zero parse failures; precision/recall 1.0 on labeled fixtures only.

Default is now CPython **3.14.8**, with **3.13.16** still required/supported. Coordinator manifest request is recorded in SHARED_CHANGE_REQUESTS.md.

Defects corrected during verification: string-valued suppression text must not suppress diagnostics; nested `str(str("text"))` must finish in one pass while preserving docstring abstention; sources need a stat check plus bounded read against growth races before parsing; rejected oversized files must not be fully read to hash them; tiny invalid parser memory budgets must fail before allocation; a pinned fixture API hash legitimately changed after formatting and was reviewed/repinned. Regression tests cover each.

**Not yet claimed complete:** standard 250,880-line benchmark, final immutable committed-source evidence and coordinator independent review. The coordinator explicitly owns that serialized standard run so this worker can release its slot. No standard run or clean-commit evidence is claimed here. Latest development evidence records actual commit plus dirty flag and exact source/lock hashes. Next action: coordinator review/commit, immutable checks and standard benchmark. Worker source writes paused at handoff.
