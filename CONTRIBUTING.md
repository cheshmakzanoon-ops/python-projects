# Development

The verification target is Linux, uv 0.12.23, and standard CPython 3.13.16 / 3.14.8. Each product owns its lockfile and environment; there is no root uv workspace. The dispatcher itself requires Python 3.11 or later. No code license has been selected; obtain permission before redistributing the code.

## Install and run

```sh
python scripts/portfolio.py doctor
python scripts/portfolio.py setup current
python scripts/portfolio.py check current
python scripts/portfolio.py demo current
```

`portfolio.toml` is the validated command and compatibility catalog. `doctor` checks packaging declarations and required files; it does not establish runtime readiness. `setup` uses `uv sync --locked` and refuses a stale or missing lock. For dependency changes, edit the owning `pyproject.toml`, run `uv lock` there, and review that lock diff. Generated state belongs under `.local/`.

On a managed cloud machine with a read-only home directory, place uv's cache and downloaded interpreters under the writable workspace:

```sh
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PYTHON_INSTALL_DIR=/workspace/.python
```

The default project environment uses its pinned CPython 3.14.8. A compatibility selector resolves to the exact patch declared in the catalog and automatically uses a separate environment:

```sh
PORTFOLIO_PYTHON=3.13 python scripts/portfolio.py setup current
PORTFOLIO_PYTHON=3.13 python scripts/portfolio.py check current
```

This uses `.local/venvs/current-3.13.16`, preserving the default editor environment. An explicit `UV_PROJECT_ENVIRONMENT` is supported for one selected product; unset it before `verify-all`, since independent products must not share an environment. The dispatcher clears inherited `PYTHONPATH` / `PYTHONHOME` and pins uv's selected working directory and project. Put additional environments under `.local/` or outside the checkout so they cannot enter source distributions or evidence hashes.

## PostgreSQL services

Run `python scripts/services.py up anchor` or `up meridian`, then export its printed local URL. The helper owns only the labeled containers `pp-anchor-dev` and `pp-meridian-dev`, binds loopback ports, and uses trust authentication for synthetic local data. It verifies ownership and bindings before managing an existing container.

`down PROJECT` removes that selected ephemeral database, its anonymous volume, and saved metadata. Start it again and export the new URL before another database workflow. Tests need database-creation privileges. Never point demonstrations or reset commands at valuable data. Each product's runbook describes its schema, migration, backup, and repair procedures; this helper is not a production provisioning tool.

## Verification

A project `check` runs formatting, lint, strict typing, the complete required test suite, source/wheel builds, and an installed-wheel demonstration outside the source directory. Each invocation owns a fresh `.local/checks/PROJECT/PYTHON/RUN/` directory containing JUnit results and build outputs. An old wheel cannot satisfy a new build. Compatibility checks for distinct interpreters have separate environments and build outputs; direct `uv` commands must provide their own isolation.

A zero exit code is insufficient: the dispatcher also requires a fresh JUnit report with at least one executed test and no failure, error, skip, or expected failure. Optional checks belong in explicitly separate suites. `PORTFOLIO_CHECK_REPORT` can select a fresh external report path for an evidence collector; an existing path is refused.

Shared checks use the quality lock:

```sh
uv sync --locked --project tooling/quality --python 3.13.16
uv run --locked --project tooling/quality pytest scripts/tests
uv run --locked --project tooling/quality ruff format --check scripts integrations
uv run --locked --project tooling/quality ruff check scripts integrations
uv run --locked --project tooling/quality mypy --strict scripts/portfolio.py scripts/select_projects.py scripts/catalog.py scripts/check_architecture.py scripts/test_results.py scripts/summarize_verification.py
python scripts/portfolio.py docs
```

The architecture tests prohibit sibling-package imports, literal dynamic sibling imports, and source import-path mutation. Integrations execute installed products through public contracts. To reproduce them, install Anchor, Meridian, Current, Quarry, PyTrace, and Atlas, start both PostgreSQL services, export their URLs, and run:

```sh
python scripts/portfolio.py integration settlement
python scripts/portfolio.py integration stream-lake
python scripts/portfolio.py integration code-search
```

Each execution owns fresh state and retains stage logs/results under `.local/integrations/`. Shared or unrecognized changes select all products in CI; normal CI tests both exact Python versions and all three integrations. The aggregate gate rejects failed, cancelled, or unexpectedly skipped jobs.

## Engineering review

A correctness fix starts with a reproducible failure through the affected public or persistence boundary. Explain the invariant, its commit/publication point, and the schedule that violates it. Use real database transactions for locking and constraint claims. A fake repository cannot establish PostgreSQL savepoint or revocation ordering.

For algorithms, derive the reference independently: exhaustive tiny assignments, a versioned dictionary, direct mathematical formulas, an external numerical implementation, or trusted fixture execution. Check intermediate decisions as well as final output. A reference model that repeats the implementation's policy can confirm the same mistake. See the [verification method](docs/architecture/VERIFICATION.md).

Add a regression where it protects a material behavior; avoid tests that merely reproduce private implementation steps. Resource claims need a deterministic work bound or a measured workload with correctness checks. Timing assertions do not belong in ordinary unit tests.

Keep production ownership in the affected product. Exchange-contract changes need the affected products and integrations. Update architecture and runbook documents when changing locks, cancellation, recovery, resource budgets, or persisted semantics. Unsupported old state must fail before mutation and have a practical operator path.

## Committed-source evidence and changes

After implementation writers stop, commit the source and run an immutable verification copy:

```sh
python scripts/verify_snapshot.py --commit HEAD --python 3.13.16 --integrations --output .local/review-python313
python scripts/verify_snapshot.py --commit HEAD --python 3.14.8 --integrations --output .local/review-python314
```

The runner clones the exact commit without sharing the index or editable environments. Each output directory must be fresh. `verification.json` inventories retained files with SHA-256 hashes, reports actual JUnit outcomes, and records requested scope. Per-product reports include source/lock/shared-input hashes and an unchanged-source check. Review failed and unrun work before treating a report as evidence. CI-sized workloads do not establish standard-workload performance.

To publish a compact matrix record, run `python scripts/summarize_verification.py .local/review-python313 .local/review-python314 --output .local/review-matrix.json`. It rechecks retained file hashes and actual JUnit outcomes, requires all products/checks/integrations on both interpreters, and refuses mixed source or shared-contract revisions. Published commands use portable executable names; raw record, log, and JUnit hashes retain their original identity. This record covers products and integrations; run shared tooling/documentation checks separately.

Historical reports remain tied to their original revisions. A later evidence/documentation commit does not retroactively enter the source it reports. Record exact commands, interpreter, revision/digests, seed, parameters, outcome, and limitations. Preserve remote history; stage explicit paths and commit coherent changes. Do not commit private inputs, credentials, environments, caches, live databases, or large generated assets.
