# Acceptance map

| Gate | Independent contract and tests |
| --- | --- |
| PY-01 | `acceptance/test_contract.py::test_py01_full_labeled_corpus`: 50 original contextual variants, 5,600 LOC, 350 declared labels; `unit/test_engine.py` adds alias/reassignment/shadowing/join/parameterization contrasts. Labels are authored without invoking the analyzer. |
| PY-02 | `test_loop_worklist_revisits_prior_sink`: source occurs after sink; a later worklist visit discovers it and iterations are bounded. Hypothesis lattice associativity/commutativity/idempotence and an independent Boolean branch-flow oracle; unknown/context/closure coverage tests. |
| PY-03 | Unicode multibyte prefix and multiline end-range test, Latin-1 fixture, syntax diagnostics, comment-only suppressions and evidence source lines. |
| PY-04 | Official OASIS SARIF schema validates repeated equivalent reports; deliberately invalid version fails. Stable identifiers and Unicode column kind asserted independently. |
| PY-05 | Real filesystem/cache tests for local edit, transitive dependency, relative imports, dependency cycle, deletion, configuration change and corrupted cache; incremental diagnostic JSON equals a clean run. `integration/test_output_safety.py` verifies source/output alias refusal and atomic cache publication/failure cleanup. |
| PY-06 | Trusted literal/API fixtures, direct trusted API old/new behavioral and error equivalence, comments/CRLF preservation, explicit apply/reanalysis, second transform is empty. |
| PY-07 | Docstring, shadow, bytes/f-string/starred/keyword constructor abstentions; conflicting API bindings/new spelling/unpacking/hash mismatch; duplicate edits, forged replacement, stale hashes, traversal, symlink, preflight no-partial-write, recovery refusing external edits. |
| PY-08 | Actual subprocess byte/node/time/address-space checks, compile-only validity, selected-root file limit, and target/setup/conftest/config sources containing sentinel-writing code that must never run. |

The subsequent [core review](CORE_REVIEW.md) adds independent checks beyond the
original correlated fixture corpus. `test_core_differential.py` compares authored
control-flow witnesses with actual CPython execution against harmless process
stand-ins. `test_solver_oracle.py` compares convergence on cyclic graphs with an
exhaustive Boolean-state interpreter and reverses successor scheduling.
`test_codemod_differential.py` executes owned before/after fixtures to compare
values, docstrings, argument order and errors. These map to PY-01/PY-02/PY-06;
normal target analysis remains non-executing.

The follow-up raise-expression cases independently execute exception-expression
failure, `from`-cause failure and finally cleanup with harmless process APIs.
Each exposes a transient alias that normal expression completion would erase;
all three failed before the raise exceptional edge was added. An equivalent
return-expression case checks the analogous already-supported path.

The CLI acceptance test invokes installed package entry points in subprocesses, produces SARIF and a reviewable patch, applies only owned trusted fixtures and verifies unchanged security findings. Unit/property tests supplement the correlated labeled variants; reported precision/recall on those variants is not an estimate of broad Python-code accuracy.

Current commands and results are in [verification history](VERIFICATION.md).
The historical standard run used source revision
`59443e2bcdfc6a1dd81f8334c108474eef2d3030`:
[raw measurements](../../../docs/evidence/final/standard/pytrace-3.14.8-benchmark-benchmark.json)
and [verification wrapper](../../../docs/evidence/final/standard/pytrace-3.14.8.json).
Its two compatibility suites each passed 77 tests. Those reports and historical
development artifacts retain their actual revisions, dirty flags and input
hashes; later tests and changes do not relabel them as current measurements.
