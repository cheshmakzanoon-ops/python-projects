# Verification history

PyTrace's acceptance map covers PY-01 through PY-08. The suite exercises lexical
bindings, fixed-point convergence, contextual taint, Unicode diagnostics, SARIF,
incremental invalidation, conservative transforms and journal recovery. Supported
interpreters are CPython 3.13.16 and 3.14.8 on Linux.

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
