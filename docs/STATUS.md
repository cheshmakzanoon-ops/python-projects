# Verification status

The [core systems review](CORE_REVIEW.md) verifies implementation `a33a513840d81f6e2cdb1b730540d906122bb254` in clean detached checkouts. It covers all ten products on CPython 3.13.16 and 3.14.8, with unchanged product, lockfile, and shared-input hashes before and after execution. The [matrix record](evidence/core-review-2026-10-20.json) binds outcomes to fresh executed JUnit cases and retained command/log hashes. Later review/evidence documentation does not change those tested implementation inputs.

## Current compatibility checks

| Product | CPython 3.13.16 | CPython 3.14.8 |
| --- | ---: | ---: |
| Anchor | 131 | 131 |
| Strata | 155 | 155 |
| Current | 159 | 159 |
| Meridian | 120 | 120 |
| Quarry | 107 | 107 |
| PyTrace | 202 | 202 |
| Atlas | 106 | 106 |
| Proving Ground | 195 | 195 |
| Routecraft | 147 | 147 |
| Resonance | 200 | 200 |

**3,044 project test executions passed**, with zero failures, errors, skips, or expected failures. Each of the twenty checks also completed locked installation, Ruff formatting/lint, strict typing, source/wheel builds, runtime-only wheel installation, and an installed-wheel demonstration outside source. Every product passed its public demo and CI-sized workload on both interpreters.

[Shared verification](evidence/core-review-shared-2026-10-20.json) separately passed **119 tests per interpreter** (238 executions), Ruff formatting/lint for scripts and integrations, and the six strict-mypy modules selected by CI. It retained actual interpreter/environment checks, fresh JUnit cases, and clean detached before/after inventories. The source documentation passed 641 local links and a strict MkDocs build; publication documentation was checked again after adding these records.

## Public integrations

All three integrations passed on both interpreters: **six executions** using independent package environments and public HTTP or JSON contracts. The matrix record validates both the outer process and the expected successful participant stages.

| Integration | Exercised boundary |
| --- | --- |
| [Settlement](../integrations/01-settlement/) | Meridian HTTP effects, Anchor worker death before acknowledgement, idempotent retry, reversal compensation, and independent SQL balance checks |
| [Stream to lake](../integrations/02-stream-lake/) | Duplicate and out-of-order revisions, retained historical identities, pinned old results, correct latest aggregates, and conflicting-history rejection |
| [Code search](../integrations/03-code-search/) | Finding publication/deletion, permission-aware search, tenant isolation, hidden-score invariance, direct-access denial, and next-request revocation |

The runner selects each participant's declared exact interpreter and separate project environment, including the nested Anchor settlement worker. Inherited source/environment selectors cannot redirect those participants to another checkout.

## Measurements, browser checks, and dependencies

The [focused comparison](evidence/core-focused-2026-10-20.json) uses committed source and five repeats for each main Current, PyTrace, Routecraft, and Resonance workload. It retains actual observations, commands, imported module/workload hashes, and before/after source inventories. The [review](CORE_REVIEW.md) explains deterministic work reductions, the controlled Routecraft module scope, increased Current RSS, and the slower complete Resonance audio analysis. Synthetic timings are descriptive.

Product browser observations retain their actual measured source identities in [Atlas verification](../projects/07-atlas/docs/VERIFICATION.md) and [Resonance verification](../projects/10-resonance/docs/VERIFICATION.md). They cover desktop/mobile behavior, selected Axe accessibility rules, and native audio playback where applicable. Earlier Meridian screens and interface checks remain part of the [prior review](QUALITY_REVIEW.md); these bounded checks are not a complete accessibility assessment.

The prior review's ten complete runtime lock exports passed pip-audit 2.10.1 with no known vulnerabilities reported for CPython 3.14.8 on Linux. All dependency locks remain byte-identical to the review baseline; this pass did not repeat the advisory query. Development tools, other marker combinations, and unknown vulnerabilities remain outside that record. See [SECURITY.md](../SECURITY.md).

## Compatibility and historical records

Read the [operator action table](CORE_REVIEW.md#compatibility-and-operator-action) before upgrading persisted data or worker binaries. Current checkpoints, Atlas tokenizer/Unicode identity, Proving Ground evidence, Strata WALs, Anchor history codecs, and Meridian migration 0006 have explicit compatibility procedures. Public demonstrations create fresh synthetic state and do not substitute for those upgrade steps.

The [evidence index](evidence/README.md) preserves earlier compatibility, independent reviews, standard workloads, and unsuccessful/superseded attempts under their original source revisions. The preceding [reliability and interface review](QUALITY_REVIEW.md) verified source `0e52603de3bfbe50094904b5c5b9620af2ac0178`: 2,274 product and 122 shared test executions. Those totals are historical, not additional executions of the final source.

Full standard-scale workloads were **not rerun for this review**. CI profiles exercise smaller workloads; final focused measurements do not update the historical full-workload capacity or throughput records. Process-fault tests do not simulate every storage or power-loss failure. Product runbooks state further algorithm and deployment limits.

## Platform and external status

The verified platform is Linux x86_64 with standard CPython 3.13.16 and 3.14.8. PostgreSQL checks used actual isolated local databases. Other operating systems and experimental interpreter builds remain unverified.

Hosted GitHub Actions is a separate observation; these local results do not establish a hosted pass. No package-registry release, public deployment, or environment publication is claimed. The cloud setup is saved as a configuration draft; applying/publishing it is separate. The owner has not selected a code license; notices and factual provenance remain intact.
