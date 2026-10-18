# Shared changes

No root-file edits requested. The coordinator's Current manifest should use package `pp_current`, CLI `current`, no service dependency, CPython 3.13.16 and 3.14.8 compatibility checks, and Linux for process-exit fault and standard memory evidence. The root demo dispatcher must choose fresh owned output directories.

Current → Quarry exchanges `results.json`, an array of objects containing job_id, operator_id, logical_result_key, revision, payload. Preserve all four delivery identity fields exactly. Latest rows are unique by the first three fields; later revisions replace payloads and older revisions must not overwrite them. For immutable delivery history, use `Journal.pending` and its Delivery values before acknowledgement. No sibling-source import is needed.
