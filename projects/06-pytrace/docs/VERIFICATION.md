# Verification history

PyTrace's acceptance map covers PY-01 through PY-08. The suite exercises lexical
bindings, fixed-point convergence, contextual taint, Unicode diagnostics, SARIF,
incremental invalidation, conservative transforms and journal recovery. Supported
interpreters are CPython 3.13.16 and 3.14.8 on Linux.

## Raise-expression follow-up: October 20, 2026

Peer differential probes found that evaluating a raised exception or its `from`
cause could fail before a later alias assignment. The CFG preserved only the
completed raise state, so a handler/finally sink could lose the earlier process
alias. Three trusted concrete fixtures reproduced the missing findings before
the fix; the analogous return-expression control already passed. Raise now
retains exceptional expression-prefix state on the enclosing continuation.
The [core review](CORE_REVIEW.md#follow-up-exceptions-while-evaluating-raise)
records the precise witness and modeled boundary.

The final suite passed **202 tests with zero failures/errors/skips on each
interpreter**: 16.48 s on CPython 3.14.8 and 15.33 s on CPython 3.13.16. Ruff
format/lint (53 checked files), strict mypy (25 source modules), sdist/wheel builds
and isolated installed-wheel demos passed for both. The focused CFG/solver/
trusted differential selection passed 38 tests. These checks used separate
environments and ran the full interpreter checks sequentially through
`PORTFOLIO_PYTHON=VERSION python scripts/portfolio.py check pytrace` from the root.

The working-tree source digest is
`aacd3998c6bff8d453dc429919b4081954c964ef2d799ee7ceb38c7dab5fdcd0`
under the source/test/benchmark/example/manifest scope declared by
`pp_pytrace.evidence.metadata`; lock SHA-256 is
`4e0752505efdd7261423861af80c8e7fb9f89ce9569d5f09be728826d5507660`.
Documentation is outside that scope. This narrow follow-up did not rerun the
earlier mechanism scaling or standard workload; those raw artifacts keep their
original source identities and do not time this final implementation.

## Compiler and dataflow review: October 20, 2026

Starting revision: `39d3a8d`. This review refactors control-flow lowering and
convergence, not the target-execution policy. [Core review](CORE_REVIEW.md)
records the defects, independently executed witnesses and exact scaling scope.

The reviewed suite contains **198 tests**. Thirteen concrete source-to-shell
witnesses all fail against an independently exported baseline package and pass
with the reviewed implementation. The preserved [failure capture](../artifacts/deep-core-baseline-failures.txt)
shows those failures; they are expected baseline defects rather than failures of
the reviewed tree. The original 50-file labeled corpus still passes unchanged.

Additional evidence includes an exhaustive finite-state solver oracle over 80
generated cyclic graphs, successor-order invariance, CPython symbol-table and
comprehension-lifetime comparisons, explicit finally/loop/exception graph checks,
and 12 before/after executions of owned codemod fixtures. Only these trusted test
fixtures execute; target analysis still parses without executing source.

The [baseline scaling report](../artifacts/deep-core-baseline-39d3a8d.json) and
[reviewed scaling report](../artifacts/deep-core-scaling.json) retain three repeats,
identical generated source hashes and imported Python-package hashes. For 900
functions, analysis-only median time changed from **2.8605 s** to **0.2454 s** on
this shared host. Parsing/cache/I/O are excluded. The mechanism comparison does
not establish end-to-end capacity or accuracy on unfamiliar repositories.

Ruff format/lint and strict mypy (25 source files) pass. Both supported
interpreters run the full suite in isolated environments: **198 passed in
16.18 s on 3.14.8**, and **198 passed in 16.23 s on 3.13.16**. Wheel/sdist builds
and installed-wheel demos pass on both versions, preserving findings and codemod
idempotence. Large historical benchmark
reports are unchanged and have not been rerun. Exception types, context-manager
suppression, `except*` subgroups, heap/closure behavior and annotation evaluation
remain documented boundaries.

## Review: October 20, 2026

This review adds regression coverage for two classes of defect:

- Analysis and preview outputs could overwrite their input source. Cache, report
  and plan destinations now reject selected source aliases, including symlinks
  and hard links; a diff cannot overwrite another Python file in its root.
  Plan and patch output paths must also be distinct.
- Cache publication used a predictable `.tmp` path, allowing an existing symlink
  to redirect a write. It now uses an exclusively created temporary and atomic
  replacement. A failed replacement preserves the old cache and removes only
  that invocation's temporary.
- Subscript and slice expressions skipped index evaluation. Taint introduced by
  a named expression in an index, and security sinks nested in an index, could
  be missed. Index/receiver effects now run in Python evaluation order for reads,
  assignment, annotation and deletion targets. Augmented assignment evaluates its target
  once, before its right-hand side.

Validation commands run from the project directory, with
`UV_CACHE_DIR=/workspace/.cache/uv` and
`UV_PYTHON_INSTALL_DIR=/workspace/.python`:

```sh
uv sync --locked --python 3.14.8
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest -q
uv build --python 3.14.8
```

Compatibility uses a separate `UV_PROJECT_ENVIRONMENT` under `.local/venvs/` and
explicit `--python 3.13.16`. Interpreter checks run sequentially because build
outputs are shared.

The final working tree passed **151 tests on each interpreter**: 11.52 s on
CPython 3.14.8 and 13.72 s on CPython 3.13.16. Ruff formatting/lint and strict mypy
(24 source files) passed. The source distribution and wheel built successfully;
the runtime-only installed-wheel demo passed outside the checkout on CPython
3.14.8, with idempotence and preserved security findings confirmed. These are
working-tree results; they do not replace immutable source records.

The current review does not rerun the standard benchmark;
all performance measurements below retain their original source revisions.

## Review: October 18, 2026

The reviewed tree passed **127 tests** on each supported interpreter. Ruff,
strict mypy (24 source files), wheel and source-distribution builds passed.
These were working-tree results, distinct from the immutable benchmark records.

The review corrected truthy shell flags, unresolved process keyword unpacking,
ambiguous sanitizers, argument evaluation order, annotation-only assignments,
conditional name writes and AST serialization of bytes, complex values and
Ellipsis. Editing regressions cover wildcard-import abstention, noncanonical
paths, malformed plans, interrupted-write recovery and long filenames. Corrupt
cache metadata rebuilds analysis. Discovery rejects symlinks and nonregular
inputs, and ignores directories whose names end in `.py`.

## Original acceptance and benchmark records

The immutable acceptance revision is
`59443e2bcdfc6a1dd81f8334c108474eef2d3030`. Its compatibility records each contain
**77 passing tests**: [CPython 3.13.16](../../../docs/evidence/final/python313/pytrace-3.13.16.json)
and [CPython 3.14.8](../../../docs/evidence/final/python314/pytrace-3.14.8.json).
These counts describe that revision and do not include later regressions.

The 50 labeled fixture files contain 5,600 source lines and 350 declared positive
cases, with negative contrasts. They establish their authored contracts rather
than independent accuracy on unfamiliar Python code. Historical core coverage
was **93.10% statements**, **88.52% branches (216/244)** and **91.72% combined**
for the declared analysis/CFG/semantics/codemod scope. Frontend, cache, reporting
and CLI were tested but excluded from that coverage scope.

The [standard measurements](../../../docs/evidence/final/standard/pytrace-3.14.8-benchmark-benchmark.json)
and [verification wrapper](../../../docs/evidence/final/standard/pytrace-3.14.8.json)
record their exact commands, source/lock hashes and input scopes. The workload
contains 234 files and 250,899 lines. One cold run took **72.576544 s**; five warm
runs had a median of **3.254818 s**. A dependency edit invalidated exactly ten
files in **1.085980 s**, with incremental findings equal to a clean run and zero
parse failures. One cold run limits timing comparisons. Precision and recall are
null for this generated scale workload.

Peak traced Python allocation was 339,695,450 bytes. Analyzer peak RSS and maximum
child peak RSS were each 960,466,944 bytes; these separate counters are not a sum
or a simultaneous machine peak. [Benchmarks](BENCHMARKS.md) retain the historical
CI measurements and their explicitly dirty development-source provenance.

The suite and source changes establish the documented behavior, not full Python
soundness, production adoption or security certification. The editing threat
model excludes hostile concurrent filesystem mutation. Recovery covers process
interruption after a valid prepared journal exists; sudden power loss and
transactional multi-file replacement remain outside its guarantee.
