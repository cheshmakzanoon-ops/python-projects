# Acceptance mapping

AT-01–AT-08 are verified through project tests, independent coordinator review and
integration. Python 3.13.16 and 3.14.8 compatibility runs each pass 40 tests, with
no required service skipped. The final required standard workload passed from
clean immutable commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`.

| Gate | Evidence / test | Contract |
|---|---|---|
| AT-01 | `tests/unit/test_lexical.py::test_at01_hand_scores_six_documents` | Six independent hand-derived scores, unique query terms, empty cases and stable ID ties |
| AT-02 | `tests/unit/test_lexical.py::test_at02_unicode_and_original_offsets`; `tests/unit/test_lexical.py::test_at02_phrase_repetition_filter_and_tie`; `tests/property/test_history.py::test_normalization_equivalence_and_source_bounds` | Canonical, compatibility and Hangul normalization, exact positions, escaped HTML and bounded grammar |
| AT-03 | `tests/integration/test_persistence_auth.py::test_at03_concurrent_generation_publication`; `tests/integration/test_persistence_auth.py::test_two_independent_writers_never_lose_published_segments`; `tests/integration/test_failures.py::test_stale_merge_rejects_concurrent_publication`; `tests/integration/test_persistence_auth.py::test_at03_at04_revision_delete_merge_restart` | Coherent generations, external merge score/position preservation and no lost writes |
| AT-04 | `tests/integration/test_persistence_auth.py::test_at03_at04_revision_delete_merge_restart`; `tests/property/test_history.py::test_catalog_history_matches_independent_ascii_model` | Superseded and deleted records never reappear through search or fetch |
| AT-05 | `tests/integration/test_persistence_auth.py::test_at05_at06_at07_permissions_cache_and_hidden_statistics`; `tests/integration/test_persistence_auth.py::test_at05_api_authorization_boundary`; code-search integration | Tenant and group isolation through snippets, totals, facets, exports, direct fetch and caches |
| AT-06 | `tests/integration/test_persistence_auth.py::test_at05_at06_at07_permissions_cache_and_hidden_statistics`; response statistics equality; code-search integration | Hidden changes preserve visible scores, snippets, counts, facets and N/df/average length |
| AT-07 | `tests/integration/test_persistence_auth.py::test_at07_corrupt_segment_even_after_cache`; `tests/integration/test_failures.py::test_valid_checksum_does_not_bypass_format_validation`; `tests/unit/test_lexical.py::test_at07_bounded_parser`; `tests/integration/test_persistence_auth.py::test_inflight_request_pins_acl_but_next_request_observes_revoke`; `tests/integration/test_persistence_auth.py::test_atomic_catalog_rollback_and_orphan_ignored`; `tests/integration/test_persistence_auth.py::test_process_dies_after_fsynced_segment_before_catalog_publication` | Next request observes revoke; malformed/corrupt input fails clearly; unpublished orphans stay invisible |
| AT-08 | `tests/acceptance/test_cli_quality.py::test_at08_frozen_quality_corpus_and_development_improvement`; `artifacts/development-quality.json`; independent semantic audit | 250 original documents, 60 graded intents, frozen 30/30 split, reported failures and development-selected phrase improvement |

Independent expected behavior comes from literal hand-score arithmetic, a simpler
ASCII document/visibility dictionary and directly calculated DCG metrics. Relevance
labels were written from intent before retrieval. The completed coordinator
[judgment review](../../../docs/evidence/atlas-judgment-review.md) records corpus
and judgment hashes, semantic checks, rubric agreement and narrow-template
limitations without consulting per-query scorer output. No judgments were changed
during review. Recall is over the authored relevant pool; human-assessor agreement
and broad natural-query relevance are not claimed.

The coordinator's code-search integration uses actual PyTrace findings through
JSON and Atlas's public API. It covers obsolete document deletion, hidden-update
score invariance, merge, tenant isolation, fetch/export, caches and revocation.

Persistence tests use actual SQLite WAL/files and separate processes that die
during an uncommitted catalog transaction or after fsynced segment output before
publication. An offline copied-root restore test validates recovery. These tests
establish process-failure boundaries, not arbitrary storage-controller or
power-loss behavior.

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest --cov=pp_atlas --cov-branch
uv build
```

Clean wheel checks install the distribution and hash-verified locked runtime
dependencies into a new environment, change cwd outside source, then execute demo,
cleanup and a CI benchmark. No PYTHONPATH source import is supplied. The complete
package, including CLI/API/benchmark/provenance code, has 97% branch-inclusive
coverage in the local 40-test run. Both required interpreter checks pass.

The [final standard benchmark](../../../docs/evidence/final/standard/atlas-3.14.8-benchmark-benchmark.json)
measures 100,000 documents × 400 tokens and 2,000 queries × five repetitions.
Authorization, expected visible count and source-stability checks are all true;
source_dirty=false and exact input hashes are recorded. The accompanying
[verification record](../../../docs/evidence/final/standard/atlas-3.14.8.json)
records successful commands and the immutable tested commit. Historical dirty
captures in `artifacts/` retain their original provenance and are not presented as
final committed evidence. See [benchmarks](BENCHMARKS.md) for actual timings,
O(N) authorization cost, memory use and relevance limits.
