# Evidence and claim boundaries

A report names the exact source it tested. Adding evidence later creates another commit; the report cannot include its own future commit. Historical records retain their original source, environment, parameters, and limitations.

## Immutable verification

Before final verification, stop implementation writers and commit the source. `scripts/verify_snapshot.py` creates a detached local clone without shared Git objects/index or editable environments. It removes inherited project/source selectors, installs independent locked environments, and runs the requested checks. The output directory must be fresh.

Per-product records contain the commit, project/lock/shared-input hashes, explicit inclusion lists, commands, exit statuses, durations, and unchanged-source result. Project scope includes implementation, tests, fixtures, examples, benchmarks, package metadata, lockfile, and interpreter declaration. Shared inputs include the dispatcher and root contract/configuration. Generated state, build outputs, environments, caches, project result artifacts, and product documentation are excluded. The inclusion list—not a vague claim to hash the entire repository—defines the digest.

The runner retains JUnit and command logs outside the disposable clone. `verification.json` records the requested products/checks/interpreter/profile, actual test totals, integration outcomes, and a SHA-256 inventory of retained files. Per-product reports provide the detailed source identities. A partial invocation establishes only that requested scope. An interrupted run without a complete successful summary cannot close the matrix.

`scripts/summarize_verification.py` publishes a compact matrix only after rechecking the retained hashes, actual JUnit cases, complete project/check/integration scope, clean unchanged source, and agreement across both interpreters. Portable command notation removes machine-specific executable/clone prefixes; raw-record and log hashes identify the original files. These hashes establish local consistency, not cryptographically signed authenticity. Shared tooling checks and focused/standard measurements remain separate evidence scopes.

## Test outcomes

Required checks must execute at least one test and have zero failures, errors, skips, or expected failures. The dispatcher reads testcase outcomes from a fresh JUnit report and checks declared summary consistency; a successful collection-only command is insufficient. Build and installed-wheel checks follow the executed tests and use that invocation's isolated output directory.

Counts describe execution, not engineering quality. Evidence for a guarantee names the invariant and the test/model that could falsify it. Independent references and controlled schedules are described in the [verification method](VERIFICATION.md). Record unrun work and failures alongside passes; do not infer acceptance from command exit status alone.

## Measurements

Benchmark evidence includes source/shared digests, lock hash, interpreter, OS/CPU, memory limit if known, seed/input identity, profile, parameters, warmup/repetition counts, thread settings, measured outputs, and correctness checks. Standard workloads run serially with numerical threads pinned. Five measurement repetitions are required unless cost justifies an explicit recorded exception.

A focused algorithm probe establishes its measured work reduction, not whole-product capacity. Concurrent-development timings remain descriptive. CI workloads verify bounded behavior; they do not replace standard-profile measurements. Synthetic numerical fixtures do not establish real-recording or real-dataset quality.

## Operational observations

Process termination exercises one recovery boundary and does not simulate every power-loss failure. A coherent backup/restore test does not establish support for arbitrary old binaries. Compatibility claims name actual supported fixtures, versions, and migration paths.

Git push, local validation, hosted CI success, saved environment configuration, and published environment settings are separate observations. State only those verified. The environment owner controls publication in environment settings. [Verification status](../STATUS.md) records the current evidence scope and external status.
