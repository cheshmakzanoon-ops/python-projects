# Evidence and claim boundaries

A report identifies the source commit it actually tested. Adding a report later creates another commit; evidence never pretends to include its own future commit. Before final verification, pause implementation writers and clone the local repository into a clean temporary directory and check out the exact detached commit. Preserve .git for product provenance. Install independent environments there and run the required commands. This is an immutable verification copy, not a development worktree.

Project digests include implementation, tests, fixtures, pyproject, uv.lock, Python declaration, benchmarks, examples, and the root dispatcher/configuration inputs. Generated results, build outputs, virtual environments, caches, project artifacts, and evidence/status documents are excluded to avoid self-reference. Record the exact inclusion list with each report. Compare the digest before and after verification. Dirty development measurements are useful but do not replace a final committed-source run.

Test records distinguish passed, failed, skipped, expected-failure, and unrun results. A zero-test run cannot close an acceptance gate. A process kill exercises recovery from process termination; it does not simulate all power-loss failures. A synthetic numerical fixture does not establish accuracy on real recordings. Performance figures are local measurements for their specified workloads, not production capacity claims.

Benchmark records include the source and root digests, lock hash, interpreter, OS/CPU, memory limit if known, seed, input identity, profile, parameters, warmup/repetition counts, metrics, and correctness checks. Standard benchmarks run serially with numerical threads pinned. At least five measurement repetitions are required unless run cost justifies a recorded exception.

Git push success, local validation, remote CI success, environment configuration saving, and environment publication are different observations. Report only what was verified. The owner controls environment publication through environment settings.
