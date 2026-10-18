# PyTrace

A Python static analyzer with an original control-flow and fixed-point dataflow engine. It finds untrusted shell commands, string-built SQL and synchronous blocking calls inside async functions, explains uncertainty, exports JSON/SARIF, and previews two narrowly justified source transformations.

```bash
uv sync --locked --python 3.14.8
uv run --locked python -m pp_pytrace.cli demo --output /tmp/pytrace-demo --seed 1729
uv run --locked python -m pp_pytrace.cli analyze examples --format text
uv run --locked python -m pp_pytrace.cli benchmark --profile ci --output /tmp/pytrace-bench --seed 1729
```

The demo writes diagnostics, official-schema-validated SARIF, a unified patch and a recoverable apply journal. It preserves security findings: shell, SQL and async risks are never auto-fixed. Targets are parsed in bounded subprocesses, never imported or executed. No service, account or paid API is required.

```bash
uv run --locked python -m pp_pytrace.cli diff /absolute/trusted/source service.py --plan /tmp/plan.json
uv run --locked python -m pp_pytrace.cli apply /tmp/plan.json --root /absolute/trusted/source --journal /tmp/apply-journal
uv run --locked python -m pp_pytrace.cli recover /tmp/apply-journal --root /absolute/trusted/source
```

The public API is `analyze(Path(root), cache=Path(cache))`. `Result.to_dict()` is the versioned integration interface; no sibling project imports are needed. CLI analysis exits zero with findings, one on parse failures or `--fail-on-findings`, and two on invalid input.

Read [architecture](docs/ARCHITECTURE.md), [analysis boundaries](docs/DECISIONS.md), [operations](docs/OPERATIONS.md), [acceptance evidence](docs/ACCEPTANCE.md), [benchmarks](docs/BENCHMARKS.md), and [case study](docs/CASE_STUDY.md). This is a portfolio implementation, not a security certification or a claim of production adoption.

Default CPython is 3.14.8 after full evaluation; CPython 3.13.16 remains in the required compatibility matrix.
