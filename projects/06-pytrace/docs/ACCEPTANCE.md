# Acceptance map

| Gate | Independent contract and tests |
| --- | --- |
| PY-01 | `acceptance/test_contract.py::test_py01_full_labeled_corpus`: 50 original contextual variants, 5,600 LOC, 350 declared labels; `unit/test_engine.py` adds alias/reassignment/shadowing/join/parameterization contrasts. Labels are authored without invoking the analyzer. |
| PY-02 | `test_loop_worklist_revisits_prior_sink`: source occurs after sink; a later worklist visit discovers it and iterations are bounded. Hypothesis lattice associativity/commutativity/idempotence and an independent Boolean branch-flow oracle; unknown/context/closure coverage tests. |
| PY-03 | Unicode multibyte prefix and multiline end-range test, Latin-1 fixture, syntax diagnostics, comment-only suppressions and evidence source lines. |
| PY-04 | Official OASIS SARIF schema validates repeated equivalent reports; deliberately invalid version fails. Stable identifiers and Unicode column kind asserted independently. |
| PY-05 | Real filesystem/cache tests for local edit, transitive dependency, relative imports, dependency cycle, deletion, configuration change and corrupted cache; incremental diagnostic JSON equals a clean run. |
| PY-06 | Trusted literal/API fixtures, direct trusted API old/new behavioral and error equivalence, comments/CRLF preservation, explicit apply/reanalysis, second transform is empty. |
| PY-07 | Docstring, shadow, bytes/f-string/starred/keyword constructor abstentions; conflicting API bindings/new spelling/unpacking/hash mismatch; duplicate edits, forged replacement, stale hashes, traversal, symlink, preflight no-partial-write, recovery refusing external edits. |
| PY-08 | Actual subprocess byte/node/time/address-space checks, compile-only validity, selected-root file limit, and target/setup/conftest/config sources containing sentinel-writing code that must never run. |

The CLI acceptance test invokes installed package entry points in subprocesses, produces SARIF and a reviewable patch, applies only owned trusted fixtures and verifies unchanged security findings. Unit/property tests supplement the correlated labeled variants; reported precision/recall on those variants is not an estimate of broad Python-code accuracy.

Verification commands and current exact results are in [AGENT_STATUS](AGENT_STATUS.md). Final repository evidence is coordinator-owned and must be rerun on an immutable committed source export. Development output always records the actual source commit, dirty flag and source/lock/root-contract hashes.
