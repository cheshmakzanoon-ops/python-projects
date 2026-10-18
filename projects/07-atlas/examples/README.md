# Original quality collection

`quality_corpus.json` contains250 original synthetic technical documents:50 topics,
each with a current runbook, design decision, incident drill, restricted operations
note and archival distractor. Restricted notes use `group:ops`; public evaluation
uses a principal with no groups. Every document is attributed to this collection.

`quality_judgments.json` contains60 manually authored intents/graded queries and a
frozen seeded30 development/30 heldout split. Labels were assigned by topic/intent
before running retrieval; the scorer never generates expected judgments. Grades
3/2/1 mean primary procedure/useful rationale/context; omitted docs are unjudged
and score0. Recall is over this authored pool. The phrase experiment measures a
narrow lexical weakness, not arbitrary semantic retrieval or production relevance.
The coordinator independently audits label semantics before final acceptance.
