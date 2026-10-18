# Acceptance mapping

Run `uv run --locked pytest` from this project. All tests are real local execution;
none skip a required service. Baseline interpreter verification is3.13.16 and3.14.8.
The coordinator independently reviews gates and verifies a committed immutable tree.

| Gate | Evidence/test | Contract |
|---|---|---|
| AT-01 | `tests/unit/test_lexical.py::test_at01_hand_scores_six_documents` | Six independent hand-derived scores, unique query terms, empty documents/corpus, stable ID ties |
| AT-02 | `test_at02_unicode_and_original_offsets`, `test_at02_phrase_repetition_filter_and_tie`; normalization property | Canonical/compatibility/Hangul normalization, repeated phrase positions, escaped HTML, bounded grammar |
| AT-03 | concurrent publication, independent writers, stale merge, revision/merge restart tests in `tests/integration/` | Generation coherence, external merge score/position preservation, no lost writes |
| AT-04 | `test_at03_at04_revision_delete_merge_restart`; stateful ASCII reference model | Superseded/deleted records never search/fetch again, including restart/merge |
| AT-05 | `test_at05_at06_at07_permissions_cache_and_hidden_statistics`, HTTP boundary test | Tenant and group isolation through results, snippets, totals, facets, export, direct fetch and caches |
| AT-06 | same hidden-statistics test; response statistics equality | Mutating only restricted text/title/type preserves visible scores, snippets, counts, facets and N/df/avg |
| AT-07 | cached corruption, checksummed malformed record, bounds, pinned revocation and crash tests | Next request observes revoke; malformed/corrupt input fails clearly; publication crash orphans remain invisible |
| AT-08 | `tests/acceptance/test_cli_quality.py::test_at08_frozen_quality_corpus_and_development_improvement`; `artifacts/development-quality.json` |250 original docs,60 pre-authored graded intents, frozen30/30 split, per-query failures, exact-phrase improvement selected on development |

Independence: hand scores use literal arithmetic, property histories compare with
an ASCII document/visibility dictionary, and metric tests calculate DCG directly.
Relevance labels were written by intent before retrieval; the coordinator performs
a separate semantic label audit without scorer access. Until that audit and final
committed measurements, AT-08/final evidence remain under coordinator review.

Required persistence tests use actual SQLite WAL/files and a separate process
that exits during an uncommitted catalog transaction, plus a process dying after
fsynced segment output but before catalog publication. These establish tested
process-failure boundaries, not arbitrary storage-controller/power-loss behavior.
An offline copied-root restore test validates the documented recovery procedure.

Quality commands:

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest --cov=pp_atlas --cov-branch
uv build
```

Clean wheel verification installs the wheel and locked runtime dependencies into
a new environment, changes cwd outside the repository, runs actual demo and
clean-demo, and also runs the installed-wheel CI benchmark. Source imports are
not supplied through PYTHONPATH. Coverage is measured over the whole package,
including CLI/API/benchmark/provenance code; the latest local40 test run passes,
with the preceding full38 test coverage run reporting97% branch-inclusive coverage.
