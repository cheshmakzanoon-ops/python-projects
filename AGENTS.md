# Portfolio development contract

The owner requests full implementation of PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md. Read that document and the relevant product contract. Delegate A01–A10 implementations to specialist sub-agents, up to the real runtime capacity; queue the remainder. Only the coordinator mutates Git and root/shared files. Workers edit only their assigned projects/NN-name directory, including tests and docs. Never stage, commit, branch, reset, clean, merge, or push from a worker. Preserve unrelated work. Do not create worktrees.

Use `UV_CACHE_DIR=/workspace/.cache/uv UV_PYTHON_INSTALL_DIR=/workspace/.python` on this cloud machine. Independent uv projects, no root workspace. Python default initially 3.13.16; 3.14.8 evaluation follows. Use `uv sync --locked --python 3.13.16` in each project. Set BLAS/OpenMP threads to 1 for benchmarks. Keep heavy benchmarks serialized. No required test may silently skip a required service.

Root commands: `python scripts/portfolio.py list|doctor`, `setup|check|demo|benchmark PROJECT`, `verify-all --jobs 2`, `docs`, and `integration settlement|stream-lake|code-search`.

Shared CLI contract for every project: `uv run --locked python -m PACKAGE.cli demo --output PATH --seed 1729`; `benchmark --profile ci|standard --output PATH --seed 1729`; `clean-demo --output PATH` (only remove explicitly owned demo state). Defaults must be safe and runnable. The root dispatcher passes an absolute output path outside tracked source. Product-specific commands may add options. JSON exchange files for integrations; never import sibling source.

Each package owns a hatchling pyproject, uv.lock, .python-version, src layout, pytest importlib mode, strict mypy and Ruff config extending ../../ruff.toml. Check commands: uv run --locked ruff format --check ., ruff check ., mypy src, pytest, uv build. Add real tests and report exact remaining acceptance IDs, failures, commands, evidence, and limitations in docs/AGENT_STATUS.md. Do not claim completion from scaffold or passing trivial tests. Use real PostgreSQL for Anchor and Meridian. Coordinator supplies local DB URLs via environment; never commit credential values.

For evidence, record source commit plus dirty flag and exact source/lock hashes. Root evidence excludes generated results, artifacts, docs/evidence and AGENT_STATUS to avoid self-reference. Final verification occurs on an exported immutable committed tree, never a moving worker snapshot. Stop writes for requested stable handoffs.
