# Supporting review records

Download the [records archive](records.tar.gz) for the detailed logs, executed JUnit reports, source inventories, compact outputs, and reproduction/publication helpers behind the review summaries. Its [manifest](manifest.json) identifies all 616 files and records the archive hash, original file hashes, and published file hashes. The archive contains approximately 5.4 MB of text compressed to 1 MB.

The final product/interpreter runs and shared checks identify implementation `a33a513840d81f6e2cdb1b730540d906122bb254`. Earlier review runs, dependency-query attempts, and focused working-tree observations retain their own actual sources and outcomes. They are historical evidence, not additional passes of the final revision. The [final matrix](../core-review-2026-10-20.json), [shared checks](../core-review-shared-2026-10-20.json), and [focused comparison](../core-focused-2026-10-20.json) remain the accepted summaries for their declared scopes.

## Contents

| Archive directory | Records |
| --- | --- |
| `core-review-final/` | Both final interpreter matrices, public integration logs, actual JUnit, shared checks, source inventories, publication helpers, and the documentation check |
| `core-review-focused-final/` | Six serial measurement outputs, commands, source inventories, validation results, and their historical execution/validation helpers |
| `quality-2026-10-20/` | Preceding reliability/interface review runs and their original outcomes |
| `strata-deep-review/` | Storage compatibility, transaction histories, and version-seek observations |
| `proving-ground-deep-review/` | Baseline failure/concurrency reproductions and bootstrap comparisons |
| `dependency-advisories-*/`, `security/` | Retained dependency-query outputs, exports, and attempts; these are not new advisory queries |

Extract into a fresh directory:

```sh
mkdir review-records
tar -xzf records.tar.gz -C review-records
```

The archive includes regular text files only, with no absolute member paths, parent traversal, or links. Every member was read back and checked against its published byte count and SHA-256. Historical helper snapshots retain their original workspace assumptions; the maintained verification entry points are `scripts/verify_snapshot.py` and `scripts/summarize_verification.py` in the repository.

## Original and published bytes

An image-specific tool-directory prefix is represented as `$RUNTIME_TOOLS`. The manifest explicitly flags each changed file and preserves both original and published byte hashes. Embedded report, artifact, and log hashes still identify the original bytes; use the manifest when comparing them with published copies. Test outcomes, source identities, parameters, and measurements are not relabeled. Hashes establish consistency of these records, not signed authenticity.

Environments, caches, package builds, disposable source clones, rendered documentation, live databases, service ownership/connection metadata, and demonstration state are excluded. Their maintained source or regeneration commands are already in Git. See the [evidence policy](../../architecture/EVIDENCE.md) for claim boundaries.
