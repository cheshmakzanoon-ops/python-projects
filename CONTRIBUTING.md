# Development

Use a supported Linux machine, uv 0.12.23, and standard CPython 3.13 or 3.14. Each project has its own lock and environment; there is deliberately no uv workspace. The owner has not chosen a code license. Please obtain permission before redistributing the code.

```sh
python scripts/portfolio.py list
python scripts/portfolio.py setup strata
python scripts/portfolio.py check strata
python scripts/portfolio.py demo strata
```

`setup` uses `uv sync --locked`; it refuses stale or missing locks. Development dependency changes are explicit: edit the selected pyproject and run `uv lock` in that project, then review its lock diff. Set `PORTFOLIO_PYTHON=3.14` to select the newer required interpreter explicitly. Heavy fault tests require Linux. The manifest records the supported platform matrix; no unsupported platform is promised to pass the POSIX durability tests.

For PostgreSQL products, run `python scripts/services.py up anchor` or `up meridian`, then export the printed local database URL. The helper owns only containers named `pp-anchor-dev` and `pp-meridian-dev`, publishes loopback ports, and uses trust authentication for synthetic local data. `down PROJECT` deletes only that selected demo container and its ephemeral database. Never point demonstrations or reset commands at valuable data. Tests need privileges to create test databases and verify database constraints. CI supplies an isolated PostgreSQL service.

The service helper verifies the `pp.owner=portfolio` label before managing an existing
container and checks loopback bindings before starting it. A matching name is insufficient.
Stopping a service removes its anonymous database volume and saved connection metadata;
start it again and export the new URL before running another database workflow.

On this cloud machine the runtime and cache directories are writable under `/workspace`:

```sh
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PYTHON_INSTALL_DIR=/workspace/.python
```

Run `uv sync --locked --project tooling/quality --python 3.13`, then `uv run --locked --project tooling/quality pytest scripts/tests` for root tooling tests and `python scripts/portfolio.py docs` for link checks and documentation build. Generated demo state belongs in `.local/`, not Git.

Keep interpreter environments separate when checking compatibility. From the repository
root, for example:

```sh
PORTFOLIO_PYTHON=3.14.8 python scripts/portfolio.py check current
UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/current-3.13.16" PORTFOLIO_PYTHON=3.13.16 python scripts/portfolio.py setup current
UV_PROJECT_ENVIRONMENT="$PWD/.local/venvs/current-3.13.16" PORTFOLIO_PYTHON=3.13.16 python scripts/portfolio.py check current
```

Run these checks sequentially: separate virtual environments still share the project's
build-output directory. Put additional environments under `.local/` or outside the checkout
so they cannot enter source distributions, documentation scans, or source-evidence hashes.

Normal CI runs project checks on both supported Python families and the three public
integrations. Integration failures fail the aggregate merge check. To reproduce the
integration job, install Anchor, Meridian, Current, Quarry, PyTrace, and Atlas, start the
two database services, export their URLs, then run:

```sh
python scripts/portfolio.py integration settlement
python scripts/portfolio.py integration stream-lake
python scripts/portfolio.py integration code-search
```

Each integration creates fresh state, records its stage logs and result under
`.local/integrations/`, and returns a nonzero exit status on failure. Add a regression that
fails for the original defect before fixing behavior; include cross-project validation
when a public exchange contract changes. Historical benchmark and acceptance records
describe their recorded revision and must not be relabeled as evidence for later changes.

Keep changes focused on one behavior or documented contract. Shared tooling and exchange-format changes need validation in every affected product and integration. Stage explicit paths, commit coherent changes, and preserve existing remote history. Conventional commit prefixes are useful (`feat`, `fix`, `test`, `docs`, `build`), but accurate scope matters more. Report failing, skipped, and unrun checks alongside passing results.

Report the exact command, interpreter, source revision/content digest, seed, result, and limitations for tests and measurements. Do not commit private inputs, tokens, caches, environments, database files, or large generated assets.
