# Control-flow and semantic review

This review starts from repository revision `39d3a8d`. It changes the compiler and
abstract interpreter rather than broadening filesystem checks. The original
acceptance and large throughput records retain their own revisions.

## Reproduced failures

The [baseline failure capture](../artifacts/deep-core-baseline-failures.txt) runs
13 authored source-to-shell fixtures against an independently exported copy of
the baseline package. All 13 fail there. The same fixtures pass on the reviewed
implementation. Tests replace process APIs with harmless collectors; neither test
runs nor production analysis launch a shell.

| Defect | Observable consequence |
| --- | --- |
| Abrupt exits bypassed finally | Shell calls in return/raise/break/continue cleanup were missed |
| Iterable evaluation and target binding shared a block | An empty loop erased an existing process-call alias |
| Handlers received only try-entry state | A sink alias assigned before an exception disappeared in the handler |
| Only statement input/output states were retained | An alias written before a later failing call was lost if normal completion would overwrite it |
| Definition-time effects were skipped | Calls in defaults and executable class suites were missed |
| Dictionary children were traversed by AST field grouping | Key/value assignment effects ran in the wrong order |
| Comparison operands ran unconditionally | A skipped later operand could erase a real tainted binding |
| Guard failure skipped later-case state | A guard's alias assignment disappeared before the next match case |
| Findings accumulated during solving | A transient resolved alias left high confidence after the complete join became uncertain |
| Missing lexical binders | Exception aliases, pattern captures and default-expression walruses could incorrectly borrow globals |

The refactor separates explicit continuations, language effects and a reusable
worklist solver. SQL method-protocol knowledge is independent of canonical call
targets, so target overflow cannot erase the structural SQL rule. Source origins
remain bounded witnesses, not an execution trace or a soundness certificate.

## Independent checks

`test_core_differential.py` executes fixed, owned snippets with fake process APIs
and checks that every observed untrusted call has a finding. Negative fixtures
cover dead code, overridden returns, loop-else behavior and unbound lexical names.
The binding prepass is compared with CPython's symbol table and its
save/restore bytecode for isolated inlined-comprehension slots.

`test_solver_oracle.py` exhaustively explores a finite concrete Boolean-state
graph for each of 80 generated cyclic graphs. Source, clear and preserve
operations are compared with the solver's may-state. Reversing successor
scheduling must produce the same semantic result. Lattice properties also include
canonical target overflow and the independent SQL protocol component.

`test_codemod_differential.py` compiles and executes only owned fixtures before
and after editing. It compares values and module/class/function docstrings for
Unicode/raw/multiline literals; API migration tests compare argument evaluation
order, results, exception types/messages and idempotence. These checks do not
execute an analyzed target or its tests.

Nested-finally lowering is checked independently for shared suffixes and explicit
budgets. Source/cleanup control flow is checked against graph reachability and
actual CPython behavior. These fixtures cover the declared subset; exception
subgroup splitting, context-manager suppression, arbitrary heap semantics and
interprocedural summaries remain outside it.

## Follow-up: exceptions while evaluating raise

A peer probe found one missed abrupt-expression boundary: `raise` routed only its
completed effects, unlike return's exceptional edge. In an owned fixture,
`raise ValueError((run := os.system), int("invalid"), (run := print))` fails before
the second alias assignment. The handler calls the retained process alias with
an input value. CPython's harmless collector observed that flow while the
analyzer missed it. An exception in a `from` cause and the same flow entering a
finally suite were also reproduced. All three differential regressions failed
before the fix; a return-expression control case passed.

Raise now routes its exceptional expression prefixes to the enclosing
handler/finally continuation, preserving pre-failure writes. The four additional
trusted cases extend the original 13 witnesses; the earlier baseline capture and
scaling reports retain their original source identities. This narrow follow-up
does not rerun or relabel those timings or expand the exception-type model.

## Focused scaling

`benchmarks/semantic_scaling.py` generates 100, 300 and 900 functions. Each has a
conditional source, a try/finally suite and a process sink. Source sizes are
10,200, 30,800 and 92,600 bytes. Each AST is parsed before timing; three repeats
include analyzer construction, lexical binding, CFG construction, convergence and
diagnostics. Parsing, cache and file I/O are excluded.

The [baseline record](../artifacts/deep-core-baseline-39d3a8d.json) imports Python
source from a Git archive of `39d3a8d`. The [reviewed record](../artifacts/deep-core-scaling.json)
imports the working-tree package. Both store identical generated source hashes,
actual imported-package paths and SHA-256 over sorted relative Python-file names,
a NUL separator and their bytes. This is a Python-code hash, not a digest of all
distribution resources.

| Functions | Baseline median | Reviewed median |
| ---: | ---: | ---: |
| 100 | 0.0410 s | 0.0263 s |
| 300 | 0.2939 s | 0.0832 s |
| 900 | 2.8605 s | 0.2454 s |

Both records retain the expected one shell finding per function. The reviewed
CFG has more explicit paths than the baseline. Profiling during development
identified irrelevant unknown globals, unconditional exceptional joins and
repeated whole-source line splitting. Sparse binding state, edge-specific joins
and a reusable source map address those costs. A naive cleanup expansion also
produced 1,824 blocks at six nested finally levels; continuation memoization
removes that exponential duplication.

These are synthetic mechanism measurements on one shared Linux host and CPython
3.14.8. They do not establish end-to-end repository throughput, real-world
accuracy, exclusive-CPU timing or production capacity. Reproduce from the project
directory:

```sh
uv run --locked --python 3.14.8 python benchmarks/semantic_scaling.py \
  --label current --output /tmp/pytrace-semantic-scaling.json
```

For the baseline, export its `projects/06-pytrace/src` subtree and select that
package with `PYTHONPATH` while running the same driver and lock. Inspect the
reported `package_path` and content hash before comparing results.
