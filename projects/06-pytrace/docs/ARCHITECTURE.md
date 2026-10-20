# Architecture

The pipeline is discovery → bounded AST parsing → lexical bindings/import graph → CFG → finite abstract interpretation → diagnostics/cache → JSON/SARIF. LibCST is used independently for reviewable formatting-preserving edits, not as the semantic analysis engine.

`cfg/blocks.py` creates statement blocks, two branch edges, loop backedges, and explicit break/continue/return exits. The exit block is index zero. Try handlers are conservatively reachable from try entry. `tests/unit/test_engine.py::test_cfg_has_hand_drawn_edges` independently enumerates the expected diamond edges.

`analysis/lattice.py` represents contextual taint bits (shell and SQL), string-construction status, unknown status and a bounded set of canonical callable targets. Target overflow becomes an absorbing top marker. Origins are bounded explanation metadata and do not determine fixed-point convergence. Assignment kills an earlier binding; joins retain may-flows. Missing branch bindings become unknown. `analysis/engine.py` propagates environments through a FIFO worklist, revisiting a block only when the finite semantic state grows. The loop regression has a sink before the source in source order and requires a later worklist visit to discover the flow.

Imports retain canonical targets through aliases and assignments. A lexical local-binding prepass prevents a use before a later local assignment from incorrectly resolving to a global import. Parameter bindings shadow globals. Nested functions are analyzed separately with captured locals unknown, accompanied by a coverage diagnostic. Comprehensions and lambdas are explicit unknown boundaries. Rules share this engine rather than performing independent text scans.

PT001 requires a configured subprocess canonical target and enabled shell (or configured `os.system`). It distinguishes unknown from configured-source taint. PT002 treats configured method names as a structural SQL execution protocol: even without receiver type information, `.execute`/`.executemany` can denote a SQL sink. This is deliberately conservative and may report a non-database method; user configuration can narrow method names. Fixed SQL with separate parameters is accepted, while interpolated SQL with parameters remains unsafe. PT003 resolves configured synchronous call targets in an async lexical function. `shlex.quote` only clears shell taint; it never clears SQL taint.

`frontend` enforces selected-root path containment, no symlinks, encoding detection, byte/node/file limits, a wall timeout including process startup, and Linux address-space/CPU limits. Parsing and compilation happen in an isolated `python -I` subprocess. The AST is returned as bounded JSON, not pickle. Compilation checks validity without executing a code object. The parent reconstructs only known `ast.AST` classes. Target modules, build hooks, executable config and plugins are never imported.

`cache.py` fingerprints content, interpreter/parser limits, semantic implementation bytes, configuration, imported local-module transitive content and the module inventory. Cycles use reachable-set closure rather than recursive hashing. A module-inventory change conservatively invalidates all files, covering previously unresolved imports. Cache JSON is disposable; it is never executable.

Cache publication uses a uniquely named, exclusively created temporary in the
destination directory and replaces the destination only after serialization
completes. Concurrent analyses may publish different snapshots; the last complete
snapshot wins, and fingerprints invalidate stale entries on the next read. This
is a disposable cache, so publication does not force directory persistence.
Preflight rejects cache/report/plan destinations that alias source by path,
symlink or hard link. It protects normal local operation, not mutation races
against another process changing the filesystem during a run.

Locations convert CPython UTF-8 byte offsets into one-based Unicode code-point columns. Each diagnostic includes a source-to-sink evidence sequence, confidence/coverage, stable content-derived identity and sink location. Suppression is recognized only in actual tokenizer comments with `# pytrace: ignore[PT001]` on the sink line. SARIF uses `unicodeCodePoints` and validates against the vendored official OASIS draft-04 schema.

Codemods use LibCST qualified names, scope and source-position metadata. A plan contains selected relative paths, original byte hashes and complete replacements. Apply rechecks every file and recomputes the conservative transformation before any write, compiles replacements in the sandbox, writes backups and a journal, and atomically replaces individual files. A multi-file apply is recoverable, not transactionally atomic. No code path automatically repairs security diagnostics.

Journal recovery covers process interruption after a valid prepared manifest exists. Backup/manifest and directory persistence are not fsynced as one protocol; sudden power loss is outside the recovery guarantee. File replacement fsync alone does not establish power-loss durability.
