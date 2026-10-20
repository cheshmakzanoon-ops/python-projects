# Integration contract

Quarry accepts files through its public `Lakehouse.ingest(path, contract=...)` interface. Integrations never import another product's source or write directly to Quarry's catalog.

Each record contains `source_namespace`, `key`, `version`, `operation` and `payload`. Preserve the upstream logical key and revision: assigning a new version to every retry defeats exact replay detection. Identical historical content is replayed safely; conflicting content at an accepted revision raises `Conflict`, even after a newer revision, deletion, retention or restart.

For an initial custom payload, supply `Contract(fields={...})`. Canonical payload JSON remains available in the `payload` column of `Snapshot(root, snapshot_id).rows("facts")`. Declared extension fields also become typed `payload__FIELD` columns. Automatic evolution permits only nullable additions.

The repository's [stream-to-lake example](../../../integrations/02-stream-lake/README.md) imports Current's window revisions, retries deliveries, preserves an old pinned result and compares the current analytical state with the greatest committed upstream revision. No database service or cloud credentials are required.
