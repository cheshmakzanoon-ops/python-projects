# Operations

Install with `uv sync --locked --python 3.14.8`. Run `uv run --locked ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `uv build`. The labeled fixtures are intentionally excluded from Ruff to keep reviewer-authored line labels fixed; they are still parsed and compiled by the acceptance suite. No database or network connection is needed after installation.

Analyze only caller-selected source: `uv run --locked pytrace analyze /absolute/source --format json --output /tmp/diagnostics.json --cache /tmp/pytrace-cache.json`. Source discovery excludes `.venv`, `.git` and `__pycache__`, rejects symlinks and enforces file limits. The API accepts `Limits` and exclusion patterns. Defaults are 512,000 bytes/file, 80,000 AST nodes/file, 10,000 files, five wall seconds/parser, 384 MiB parser address space and three CPU seconds. Linux applies `resource` limits; Windows lacks address-space/CPU enforcement and retains byte/node/count/time limits. Linux is the verified target. AST grammar follows the selected interpreter; LibCST grammar support can be narrower and uncertain codemods abstain by failing safely before writes.

Use `analyze --config /tmp/config.json` for declarative call summaries. The file is bounded to 32 KB, known fields, 100 canonical names/field and 200 characters/name. Never put secrets into source summaries. Executable configuration files and target plugins are not loaded.

Control-flow lowering has a 20,000-block budget per suite; the solver has a
100,000-transfer budget per solve. Exceeding either is a controlled analysis error
(CLI status 2), with no complete result or replacement cache published. Split an
unusually large generated module or inspect its nested cleanup structure rather
than accepting an incomplete report. These work limits do not promise a fixed
wall time or whole-process memory ceiling.

Read PT900 alongside the security findings. Exception type matching is a
may-match approximation; `except*` subgroups, context-manager suppression, heap
protocols, general closures and annotation evaluation need manual review.
`finally` executes on modeled abrupt exits, and exception prefixes preserve writes
made before a later expression fails. `--fail-on-findings` includes coverage
warnings. [Rule semantics](RULES.md) gives concrete examples and interpretation.

`explain ROOT IDENTIFIER` reanalyzes the selected source and emits the matching diagnostic and evidence. `cache inspect CACHE` shows cache paths, content hashes and imports. Delete an owned cache to force a clean run; corrupted JSON also triggers rebuild. Never treat cache files from another writer as authoritative verification. Output diagnostics have `schema_version: 1`; future incompatible versions require explicit migration.

Keep report, plan, patch and cache destinations separate from source. Preflight
refuses destinations that alias analyzed Python files, including symlinks and hard
links; plan and patch destinations must also be distinct. A cache update replaces
only a complete serialized result. Failed publication preserves the prior cache
and cleans up its own uniquely named `.pytrace-cache-*.tmp` file. Abrupt process
termination can leave such a temporary; remove it only when no analyzer is using
that directory. Cache files are not a backup or a durable verification record.

For edits, preview first with `diff ROOT file.py --plan /tmp/plan.json`. Explicit apply requires `apply /tmp/plan.json --root ROOT --journal /tmp/new-journal`. The independently selected `--root` must match the saved plan. A journal directory must not already exist. Stale hashes, traversal, symlinks, duplicated edits, unsupported replacements or invalid syntax fail before writes. After an interruption, inspect `plan.json`, `complete`, and backups in the journal; run `recover JOURNAL --root ROOT` to restore originals. Recovery refuses content changed after the apply and never overwrites it silently.

Demos/benchmarks require absolute empty or explicitly owned directories. `clean-demo --output ABS` removes fixed generated state under a matching owner marker. Unrelated files at the output root remain. Do not store user documents inside generated `trusted`, `corpus`, `cache` or `journal` directories; those are owned demo namespaces. Reset never deletes arbitrary source trees.

JSON integration uses paths relative to the selected root, stable diagnostic IDs, one-based Unicode locations, evidence messages and explicit confidence/coverage. An analyzer finding calls for review; it is not a certification or a recommended automatic security patch.

Journal recovery covers process interruption after a valid prepared manifest exists. Backup/manifest and directory persistence are not fsynced as one protocol; sudden power loss is outside the recovery guarantee. File replacement fsync alone does not establish power-loss durability.

An abrupt process termination can leave a uniquely named `.pytrace-*.tmp` beside a selected source file. Recovery uses a fresh temporary, so an orphan does not prevent restoring the journal. Failed writes clean up their own temporary; unrelated files are preserved.

Default CPython is 3.14.8 after full evaluation; CPython 3.13.16 remains in the required compatibility matrix.
