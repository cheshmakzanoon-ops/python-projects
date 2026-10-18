# Operations

Use the existing repository checkout; each cloud task is already isolated. Do not
create a worktree. Run `uv sync --locked --python 3.14.8` here. Python 3.13.16 is
also checked. No database server or credentials are required.

## Search and administration

```sh
uv run --locked atlas ingest --root /tmp/atlas-index --tenant docs --input examples/quality_corpus.json
uv run --locked atlas search --root /tmp/atlas-index --tenant docs --subject alice '"wal recovery"'
uv run --locked atlas groups --root /tmp/atlas-index --tenant docs --subject alice --group ops
uv run --locked atlas acl --root /tmp/atlas-index --tenant docs topic-00-runbook --allow user:alice
uv run --locked atlas fetch --root /tmp/atlas-index --tenant docs --subject alice topic-00-runbook
uv run --locked atlas merge --root /tmp/atlas-index --tenant docs
uv run --locked atlas inspect --root /tmp/atlas-index --tenant docs
uv run --locked atlas delete --root /tmp/atlas-index --tenant docs topic-00-runbook
```

The corpus JSON contract is schema_version=1 plus a documents array, each carrying
id, title, text, ACL list and string metadata dictionary. Ingestion reads only the
explicitly selected file and bounds it at20 MB; path-like document IDs are data.
Updates use the same ingest/upsert interface. `set_acl` replaces the full ACL, so
revocation is unambiguous. Empty ACL denies everyone; `*` means authenticated
principals within this tenant. `user:NAME` and `group:NAME` are the other subjects.

## Local HTTP/search view

Configure `ATLAS_TOKEN_BINDINGS` securely as a JSON object mapping bearer strings
(at least16 characters) to `{tenant,subject,admin}` objects. Do not commit real token
values or put them in chat. For a synthetic loopback demonstration only:

```sh
ATLAS_TOKEN_BINDINGS='{"local-only-demo-token":{"tenant":"docs","subject":"alice","admin":true}}' \
  uv run --locked atlas serve --root /tmp/atlas-index --port 8107
```

Open http://127.0.0.1:8107/ and enter the synthetic token in the password field.
The view does not store tokens. API docs are at `/docs`. GET `/health` reports
process liveness; authenticated `/ready` loads and validates the tenant index.
All search/fetch/export operations require bearer authentication. POST documents,
DELETE documents/{id}, PUT documents/{id}/acl, PUT groups/{subject}, POST merge
require this tenant's admin binding. Export/search are paginated. The adapter caps
request bodies at2.1 MB and rejects extra document fields such as tenant/groups.
Do not expose the local static-token demonstration publicly; use a proper TLS and
identity boundary if deploying in a separate task. Stop with Ctrl-C; no background
process is spawned by demo or benchmark commands.

## Backup, restore and integrity failure

For this reference implementation, stop all writers, copy the complete index root
(including every tenant catalog, SQLite WAL if present, and segment directory) to
a new empty destination, and then resume writers. `shutil.copytree(source, backup)`
provides a portable offline copy. Restore into a new empty root and instantiate
`Engine(restored_root)`; compare `inspect`, search and fetch results before
replacing any existing root. Never copy only the database while omitting segments.
An integration test exercises a real copied-root restore.

To reproduce failure only in disposable owned demo state: run demo, alter bytes
in one `.jsonl.gz` under its `state` subtree, then run inspect/search. Atlas raises
`CorruptSegment`; HTTP returns503 without private content. Restore the entire
coherent backup; do not update recorded checksums to match corrupted bytes.
Unknown format/tokenizer versions require an explicit migration or rebuild from
trusted source documents, not permissive fallback.

Old segments and crash orphans are retained. The safe disk reclamation procedure
is an offline rebuild into a fresh root from trusted exported current revisions,
followed by validation and a controlled root switch. Never delete segments from
a live root because readers may still pin them.

## Owned output cleanup

`clean-demo --output /absolute/path` accepts only an Atlas ownership marker and
known output files/state. It refuses symlink paths, filesystem roots, unowned
nonempty directories and unexpected files. User files remain untouched on refusal.
Run cleanup before rerunning a demo/benchmark at the same output location.
