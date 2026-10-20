# Decisions and analysis boundary

**Original intraprocedural analysis over a finite lattice.** Whole-program Python soundness would require modeling monkeypatching, descriptors, heap aliases, metaclasses and runtime reflection. We instead document the modeled subset and emit PT900 for unknown calls, closures, reflection, exception/context/match constructs, comprehensions and heap mutation. Unknown data reaching a known sink is a diagnostic with uncertain confidence. A missing risk diagnostic across an unsupported boundary does not prove safety.

The engine is flow-sensitive for names, and path-insensitive at joins. It does not prove branch predicates or correlate two separate conditions. Function calls do not propagate user-function summaries. Mutable object fields, descriptors, comprehensions and closure captures have partial coverage. Try handlers receive exceptional state from protected operations, including recorded expression prefixes. Finally continuations preserve or override pending returns, raises and loop exits. Exception types, `except*` subgroups and context-manager suppression remain conservative boundaries. Imported APIs are assumed not to undergo runtime monkeypatching; lexical rebinding is modeled. Module functions use the module's terminal bindings as a static approximation, not a model of every import-time call ordering.

Heap values remain unknown, but evaluating a subscript or mutation target still
evaluates its receiver and index. Assignment expressions in those positions
update name state and nested sinks produce diagnostics. Augmented assignment
evaluates the target once before the right-hand side; repeating it during binding
would introduce false flows and violate Python's evaluation order.

**Origins are separate from semantics.** Adding textual evidence to the convergence key would allow an unbounded loop trace and make termination depend on explanatory strings. The semantic lattice contains finite flags and bounded target sets; provenance is independently bounded. Confidence is separate from severity. A PT900 coverage warning is not proof that a particular vulnerability exists.

**SQL execution is configured by method protocol.** Without a type checker, an unresolved receiver's `.execute` can be either a database cursor or another API. Treating all unresolved methods as safe would lose common cursor-parameter cases. The default conservative protocol may produce false positives; explicitly configure it for the target codebase. Supported parameterization requires fixed query text and a distinct argument value. Interpolated queries remain findings even when a second parameter tuple exists.

**LibCST edits, AST semantics.** Text replacement cannot reliably preserve comments or distinguish shadowed names. Qualified-name and scope metadata supply lexical preconditions; a bounded AST prepass excludes first expression statements that would become docstrings. Eligible literal calls require one explicit positional text literal, no unpacking, keyword, bytes or f-string, and no internal comment ambiguity. Inline trailing comments and original line endings are preserved. Literal text containing `#` is conservatively left unchanged. Removing the built-in call assumes no runtime rebinding or observation through reflection/tracing; those observations are outside equivalence.

The API migration supports exactly the pinned repository fixture version/hash. One explicit old keyword, no new spelling, no starred arguments, and one imported canonical binding are required. The value expression remains in exactly the same position and is not evaluated by PyTrace. Ambiguous imports, dynamic local aliases and stale manifests abstain. The trusted fixture's direct-call tests compare results and error types/messages for both spellings; target programs are never used as an execution oracle.

A wildcard import causes the module to abstain from both codemods: qualified-name metadata cannot enumerate names introduced by that import, so it cannot prove a built-in or imported API binding remains unshadowed.

**Continuations over ad hoc exit edges.** Routing every return to a single exit
skips executable cleanup. CFG lowering now carries explicit destinations for
normal completion, return, raise, break and continue. A cleanup suite is shared
only when its syntax and continuation agree. This retains pending-exit semantics
without the exponential duplication observed in a naive nested-finally builder.
Block and solver work limits fail explicitly instead of manufacturing a complete
result when analysis exceeds its budget.

Explicit raise evaluation also retains exceptional expression prefixes. A failure
in the exception expression or its `from` cause can occur before the nominal
raise, leaving different name bindings for a handler or finally suite. Treating
only completed raise effects loses those bindings even though the destination is
the same. Trusted differential fixtures cover both operands and finally cleanup;
return has the analogous exceptional edge, while break/continue have no operands.

**Solve first, report second.** Reporting during convergence made confidence
depend on whether a short branch or a long branch reached a sink first. The
solver now returns incoming fixed-point states; a separate pass emits findings.
An exhaustive Boolean-state oracle checks cyclic graphs and reversed successor
orders independently of Python transfer rules. Authored Python fixtures execute
against harmless process stand-ins to check observed source-to-sink paths;
actual target programs remain non-executing.

**Sparse unknowns and reusable locations.** Absence already means unknown in the
name environment, so storing a default unknown value for every unrelated function
adds no information. Omitting these bindings prevents module inventory from
becoming a quadratic cost in every function. Exceptional joins are computed only
for real exception edges. Source lines are indexed once for Unicode locations.
The [focused scaling record](CORE_REVIEW.md) states the exact generated workload,
source hashes and limits of the measured comparison.

**Recoverability over false atomicity.** Filesystem replacement is atomic per selected file, but multiple files are not one transaction. Apply validates all paths/hashes/replacements before creating the journal. Backups allow explicit recovery, which refuses subsequent external edits and corrupted backup hashes. Concurrent hostile filesystem mutation remains outside the local trusted editing threat model; do not apply while another writer edits the same selected files. No claim of a race-free hostile-filesystem sandbox is made.

**No code license invented.** The repository owner has not chosen a code license. Original code and synthetic corpus have no assumed redistribution grant beyond repository availability. Recommend an explicit MIT or Apache-2.0 decision by the owner. Dependency and OASIS schema notices are tracked separately.

Journal recovery covers process interruption after a valid prepared manifest exists. Backup/manifest and directory persistence are not fsynced as one protocol; sudden power loss is outside the recovery guarantee. File replacement fsync alone does not establish power-loss durability.
