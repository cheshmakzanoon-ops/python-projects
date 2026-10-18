# Operations

Install with `uv sync --locked --python 3.14.8`. Run `uv run --locked ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `uv build`. The labeled fixtures are intentionally excluded from Ruff to keep reviewer-authored line labels fixed; they are still parsed and compiled by the acceptance suite. No database or network connection is needed after installation.

Analyze only caller-selected source: `uv run --locked pytrace analyze /absolute/source --format json --output /tmp/diagnostics.json --cache /tmp/pytrace-cache.json`. Source discovery excludes `.venv`, `.git` and `__pycache__`, rejects symlinks and enforces file limits. The API accepts `Limits` and exclusion patterns. Defaults are 512,000 bytes/file, 80,000 AST nodes/file, 10,000 files, five wall seconds/parser, 384 MiB parser address space and three CPU seconds. Linux applies `resource` limits; Windows lacks address-space/CPU enforcement and retains byte/node/count/time limits. Linux is the verified target. AST grammar follows the selected interpreter; LibCST grammar support can be narrower and uncertain codemods abstain by failing safely before writes.

Use `analyze --config /tmp/config.json` for declarative call summaries. The file is bounded to 32 KB, known fields, 100 canonical names/field and 200 characters/name. Never put secrets into source summaries. Executable configuration files and target plugins are not loaded.

`explain ROOT IDENTIFIER` reanalyzes the selected source and emits the matching diagnostic and evidence. `cache inspect CACHE` shows cache paths, content hashes and imports. Delete an owned cache to force a clean run; corrupted JSON also triggers rebuild. Never treat cache files from another writer as authoritative verification. Output diagnostics have `schema_version: 1`; future incompatible versions require explicit migration.

For edits, preview first with `diff ROOT file.py --plan /tmp/plan.json`. Explicit apply requires `apply /tmp/plan.json --root ROOT --journal /tmp/new-journal`. The independently selected `--root` must match the saved plan. A journal directory must not already exist. Stale hashes, traversal, symlinks, duplicated edits, unsupported replacements or invalid syntax fail before writes. After an interruption, inspect `plan.json`, `complete`, and backups in the journal; run `recover JOURNAL --root ROOT` to restore originals. Recovery refuses content changed after the apply and never overwrites it silently.

Demos/benchmarks require absolute empty or explicitly owned directories. `clean-demo --output ABS` removes fixed generated state under a matching owner marker. Unrelated files at the output root remain. Do not store user documents inside generated `trusted`, `corpus`, `cache` or `journal` directories; those are owned demo namespaces. Reset never deletes arbitrary source trees.

JSON integration uses paths relative to the selected root, stable diagnostic IDs, one-based Unicode locations, evidence messages and explicit confidence/coverage. An analyzer finding is a review prompt, not a certification or a recommended automatic security patch.

Journal recovery covers process interruption after a valid prepared manifest exists. Backup/manifest and directory persistence are not fsynced as one protocol; sudden power loss is outside the recovery guarantee. File replacement fsync alone does not establish power-loss durability.

Default CPython is 3.14.8 after full evaluation; CPython 3.13.16 remains in the required compatibility matrix.
