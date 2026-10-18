# Atlas relevance judgment review

Coordinator review of the authored corpus and query intents, before final portfolio verification. The implementation owner authored the fixture set and judgments; this review did not consult per-query ranking outputs or derive labels from the scorer. No judgments were changed during review.

- Corpus SHA-256: `e3f24f2f08379dae885622179cd58765a72f54797d42b0acb83decf073e6bec1`.
- Judgment SHA-256: `eccefbe08f5525d9168229f6bbffe6b8636cc4276cb4da5d0a0df75f3f88854c`.
- Scope: 250 original documents, 60 graded queries, fixed 30 development / 30 held-out split.

All 50 current-guidance query families have an explicit operational intent. The corresponding runbook provides an actionable procedure (grade 3); design rationale explains the mechanism (grade 2); the incident drill supplies context (grade 1). The archival document explicitly disclaims current operational guidance and therefore receives zero for that intent. Restricted drill notes are outside the public reader's pool. All ten type-filtered procedure queries label the matching runbook; non-runbooks fail their explicit filter. All referenced documents exist and all positively graded documents are public under the declared evaluation principal.

Semantic spot checks read complete procedures for snapshot isolation, binding-safe refactoring, control-flow liveness, train-only preprocessing, waiting/service time propagation, readiness, child-process cleanup, memory bounds, Unicode source offsets, and tenant-path handling. These procedures match the authored symptoms and stated current-guidance intents. In particular, the source-offset topic means Unicode snippet positions; the query's stated intent disambiguates it from stream source offsets.

The corpus is deliberately narrow and uses repeated technical-document templates. The topic/intent rubric explains the relative grades, but it cannot establish natural-query relevance or agreement among human assessors. Recall is over the declared judgment pool. Phrase-versus-bag comparisons expose the authored archival-noise case; they do not establish broad ranking superiority. Keep development and held-out roles fixed, report per-query failures, and reevaluate this review if the corpus, intents, or grades change.
