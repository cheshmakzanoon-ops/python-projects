# PyTrace

PyTrace analyzes Python source for unsafe shell commands, string-built SQL and
blocking calls in asynchronous functions. Its control-flow graph and finite
fixed-point engine follow assignments, aliases, branches and loops; diagnostics
include the relevant source locations and an explanation of uncertainty.

Analysis reads source without importing target modules, loading plugins or running
build hooks. JSON and SARIF reports support automated review. Two conservative
LibCST transformations produce a patch for review: redundant literal `str()` calls
and a keyword migration for a pinned fixture API. Security findings require manual
review and are never automatically rewritten.

## Quick start

Run from `projects/06-pytrace` with uv 0.12.23. Linux and CPython 3.14.8 are the
default development platform; CPython 3.13.16 is also tested. No database, account
or external service is needed after installing dependencies.

```sh
uv sync --locked --python 3.14.8
uv run --locked pytrace analyze examples --format text
uv run --locked pytrace demo --output /tmp/pytrace-demo --seed 1729
```

The demo creates synthetic source and writes diagnostics, schema-validated SARIF,
a unified patch and an application journal. It applies eligible edits, verifies
idempotence and confirms that security findings remain. Use a fresh output
directory, or remove only the demo's owned state before repeating it:

```sh
uv run --locked pytrace clean-demo --output /tmp/pytrace-demo
```

## Analyze a codebase

```sh
uv run --locked pytrace analyze /absolute/source \
  --format sarif --output /tmp/findings.sarif --cache /tmp/pytrace-cache.json \
  --fail-on-findings
```

Reports and caches must not alias selected source files, including through hard
links or symlinks. Cache data is disposable and does not establish a clean
verification result. `--fail-on-findings` treats any diagnostic, including a
coverage warning, as a failing result.

| Exit status | Meaning |
| --- | --- |
| `0` | Analysis completed; findings may exist unless `--fail-on-findings` was supplied |
| `1` | Source parsing failed, or `--fail-on-findings` found diagnostics |
| `2` | Invalid arguments, configuration or filesystem operation |

For Python callers:

```python
from pathlib import Path
from pp_pytrace.cache import analyze

result = analyze(Path("/absolute/source"), cache=Path("/tmp/pytrace-cache.json"))
for diagnostic in result.diagnostics:
    print(diagnostic.rule_id, diagnostic.path, diagnostic.location.line)
report = result.to_dict()  # Versioned JSON integration contract.
```

## Review and apply an edit

```sh
uv run --locked pytrace diff /absolute/source service.py --plan /tmp/plan.json
uv run --locked pytrace apply /tmp/plan.json \
  --root /absolute/source --journal /tmp/new-apply-journal
uv run --locked pytrace recover /tmp/new-apply-journal --root /absolute/source
```

Apply rechecks content hashes and transformation eligibility for every selected
file before writing. Recovery refuses subsequent external edits. Each file
replacement is atomic; a multi-file application is recoverable through its
journal but is not a filesystem transaction. Do not edit selected files from
another process during apply or recovery.

## Engineering reference

- [Architecture](docs/ARCHITECTURE.md): CFG, lattice, bindings, cache and report contracts.
- [Rule semantics](docs/RULES.md): explainable shell, SQL and async findings, confidence and coverage.
- [Analysis boundaries](docs/DECISIONS.md): modeled Python behavior and edit preconditions.
- [Operations](docs/OPERATIONS.md): parser budgets, configuration, recovery and cleanup.
- [Acceptance map](docs/ACCEPTANCE.md) and [verification history](docs/VERIFICATION.md): reproducible checks and recorded results.
- [Benchmarks](docs/BENCHMARKS.md) and [case study](docs/CASE_STUDY.md): measurements, defects and tradeoffs.
- [Core review](docs/CORE_REVIEW.md): differential execution, convergence checks and focused scaling against a fixed baseline.

The analyzer is intraprocedural and path-insensitive. Unsupported dynamic
behavior produces coverage warnings; an absence of findings does not establish
security. Synthetic accuracy fixtures and throughput measurements do not imply
accuracy on an arbitrary codebase.
