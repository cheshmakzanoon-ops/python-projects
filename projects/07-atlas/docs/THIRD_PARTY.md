# Provenance and licensing

The 250-document technical knowledge base and60 query intents/graded judgments in
`examples/` are original synthetic fixtures written for Atlas. They describe
hypothetical engineering scenarios, not customer incidents or production usage.
The scale benchmark generates all text from the checked-in seeded generator.
No external dataset, copied implementation, model, image, or proprietary service
is required. No model downloads or reranking dependency exists.

BM25's formula is the specified Okapi variant; conceptual reference:
https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html
Unicode normalization behavior follows Python's unicodedata and Unicode data:
https://docs.python.org/3/library/unicodedata.html
SQLite supplies catalog transactions, not the retrieval implementation.
FastAPI/Pydantic handle HTTP schema validation; Python stdlib supplies gzip,
SHA-256, heap merging and SQLite bindings. Exact third-party versions and package
source distributions are recorded in uv.lock. Dependency licenses remain their
respective upstream licenses; consult installed package metadata before reuse.

The repository owner has not selected a code/data distribution license. No SPDX
identifier or redistribution permission is invented here. Recommendation: the
owner should choose and add an appropriate license before inviting reuse.
