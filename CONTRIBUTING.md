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

On this cloud machine the runtime and cache directories are writable under `/workspace`:

```sh
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PYTHON_INSTALL_DIR=/workspace/.python
```

Run `uv sync --locked --project tooling/quality --python 3.13`, then `uv run --locked --project tooling/quality pytest scripts/tests` for root tooling tests and `python scripts/portfolio.py docs` for link checks and documentation build. Generated demo state belongs in `.local/`, not Git.

Project owners format only their directories. Shared changes require coordination. A single coordinator owns Git mutations on main. Review stable project snapshots, stage explicit paths, commit coherent changes, and preserve existing remote history. Conventional commit prefixes are useful (`feat`, `fix`, `test`, `docs`, `build`) but accurate scope matters more. A passing test is evidence for its assertions, not a license to claim every acceptance requirement.

Report the exact command, interpreter, source revision/content digest, seed, result, and limitations for tests and measurements. Do not commit private inputs, tokens, caches, environments, database files, or large generated assets.
