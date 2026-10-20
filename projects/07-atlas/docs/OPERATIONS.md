# Operations

Atlas stores its own SQLite catalogs and segment files; no external database or
remote credentials are required. Install locked dependencies with
`uv sync --locked --python 3.14.8`. Python 3.13.16 is also supported, using a
separate environment and a different persisted Unicode tokenizer identity.
Linux is the tested filesystem/fsync platform.

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

Corpus JSON has `schema_version=1` and a `documents` array; each document contains
id, title, text, ACL list and string metadata. The explicit input file is bounded
at 20 MB. Document IDs are data, including path-like IDs. Re-ingest replaces current
IDs; it is not a request-id deduplication mechanism. `set_acl` replaces the entire
ACL. Empty ACL denies everyone; `*` allows authenticated principals within this
tenant. Other entries are `user:NAME` and `group:NAME`. Administrator HTTP role
authorizes mutation but does not implicitly grant read access to private documents.

`inspect` loads and verifies a tenant before reporting its generation, ACL revision,
document/term counts and segment count. It is a trusted administrative operation.
A high segment count increases every request's stat work and cold loading; merge
reduces the referenced set but deliberately retains old files on disk. Run merge
during low ingestion activity. HTTP 409 / library `StaleGeneration` means a data
writer won publication; retry the whole merge from a new snapshot. ACL-only
revocation can commit during a merge without being overwritten.

## Local HTTP and search view

Configure `ATLAS_TOKEN_BINDINGS` securely as a JSON object mapping bearer values
(at least 16 characters) to `{tenant,subject,admin}` objects. `admin` must be a JSON
boolean. Groups are read from the catalog, never supplied by the client. For a
synthetic loopback demonstration:

```sh
ATLAS_TOKEN_BINDINGS='{"local-only-demo-token":{"tenant":"docs","subject":"alice","admin":true}}' \
  uv run --locked atlas serve --root /tmp/atlas-index --port 8107
```

Open http://127.0.0.1:8107/ and enter that synthetic token in the password field.
The page holds it only in memory; connection changes/page exit clear it. No token
form name, URL parameter or browser storage is used. See the
[HTTP/browser guide](HTTP_API.md) for paging, privacy and errors.

GET `/health` is process liveness. Authenticated `/ready` validates the tenant and
returns only `{"status":"ready"}`. A healthy process can still have an unavailable
index: integrity or compatibility failures return 503 without document details.
Opening an existing catalog first recognizes it read-only. Atlas refuses unrelated
databases, incomplete schemas and missing headers rather than creating replacement
tables or default state. Restore/rebuild from a coherent source; do not use startup
as a schema repair operation. Catalog and existing WAL content remain unchanged on
rejection, although SQLite may create/update read-coordination WAL/SHM sidecars.
Fresh empty databases initialize atomically; concurrent first opens serialize through
the SQLite initialization lock. A recognized format-1 DELETE-mode catalog can convert
to WAL without rebuilding its tables or metadata.
Search/fetch/export need a reader binding; ingestion/deletion, ACL/group mutation
and merge need this tenant's administrator role. The body limit is 2.1 MB,
including chunked input. Query execution is synchronous and runs off the ASGI event
loop. One Engine serializes its own operations; each additional process keeps its
own materialized index in memory. Budget total memory across workers and tenants.

This static-token service is a local adapter. A separate deployment needs TLS,
identity lifecycle ownership and suitable log handling; query strings can appear
in access logs. Keep real bindings outside source control. Stop the foreground
server with Ctrl-C; demonstration commands do not leave background processes.

## Process failure and ambiguous responses

| Failure point | Durable catalog outcome | Recovery |
| --- | --- | --- |
| During temporary segment write | Previous generation | Restart; temporary files are unreferenced |
| After segment fsync/rename, before catalog commit | Previous generation plus ignored orphan | Restart and inspect; do not infer publication from files |
| During an open publication transaction | SQLite rolls back the transaction | Restart; verify the prior document through fetch/search |
| After commit, before acknowledgment | New revision is committed | Fetch the ID and compare intended content before retrying |
| Merge loses its generation comparison | Concurrent writer remains current | Retry merge; unpublished merge output is an orphan |
| Referenced file missing/damaged or unsupported version | Request fails; no partial result is served | Restore/rebuild into a fresh root; keep the damaged source for diagnosis |

Tests kill actual subprocesses before publication and after commit. These are
process-failure checks, not arbitrary power-loss/storage-controller guarantees.
Directory fsync is required on Linux; unsupported filesystems may reject writes.
Do not convert an integrity failure into success by editing the manifest checksum,
forcing a version string or deleting active catalog rows.

## Backup and restore

Stop **all** reader, writer and maintenance processes using the root. Confirm no
other host/process shares it. Clean shutdown normally checkpoints/removes WAL files;
after an abrupt death explicitly checkpoint each tenant while still offline:

```sh
uv run --locked python - /absolute/atlas-root <<'PY'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

for path in Path(sys.argv[1]).glob("*/catalog.sqlite3"):
    with closing(sqlite3.connect(path)) as connection:
        busy, _, _ = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy:
            raise SystemExit(f"catalog still in use: {path}")
PY
```

Copy the complete stopped root to a new, nonexistent backup destination, including
all catalogs, any remaining SQLite sidecars and segments. For example:

```sh
uv run --locked python - /absolute/atlas-root /absolute/atlas-backup <<'PY'
import shutil
import sys
shutil.copytree(sys.argv[1], sys.argv[2])
PY
```

Restart only after the copy completes. Restore a coherent backup into a new root,
using the matching interpreter/tokenizer version. Run inspect and representative
positive/negative authorization queries before restarting the service on that root.
Never copy only a catalog or replace files under running readers: caches depend on
the published revision protocol. Do not delete old segments from a live root.

## Tokenizer upgrade or interpreter switch

V1 indexed some NFKC-equivalent Japanese strings differently. V2 fixes normalization
boundaries and includes the Unicode database in its identity. Python 3.13.16 uses
UCD15.1.0; 3.14.8 uses UCD16.0.0. Switching between them requires rebuilding, even
though both use catalog/segment layout format 1. Unknown source formats/tokenizers
are refused; this is not an arbitrary future-version migration tool.

The supported path uses `pp_atlas.maintenance`, included in the installed wheel:

1. Inventory every configured **original tenant ID**; hashed directory names cannot
   recover them. Stop all old readers/writers, checkpoint and retain a complete
   backup as above. Preserve the old executable/lock/interpreter for rollback.
2. Install the selected new runtime. Keep its service stopped. Use the offline,
   checkpointed backup as source and a **nonexistent** destination outside it:

   ```sh
   uv run --locked python -m pp_atlas.maintenance \
     --source /absolute/atlas-backup \
     --destination /absolute/atlas-rebuilt \
     --tenant docs --tenant engineering
   ```

   Repeat `--tenant` for every configured tenant in this single invocation. The
   command refuses an existing destination, nested source destination, duplicate
   tenant, unsupported header, nonempty WAL, damaged segment or absent current
   revision. It reads the source SQLite file in immutable read-only mode and
   verifies every referenced segment checksum/header. A source corpus export is
   unnecessary when the current text and metadata in that index are intact.
3. Review its per-tenant document/group-record counts and source generation. The
   rebuild copies only active revisions, retains title/text/metadata/ACLs and all
   server-side group records, and retokenizes under the destination interpreter.
   Deleted/superseded records, orphans and obsolete files are not copied. Destination
   revision IDs and generation/ACL counters are new; do not compare them numerically
   with the old root or use them as durable external document identities.
4. Inspect every destination tenant. Test known searches, allowed/forbidden fetches,
   group membership and revocation. Japanese compatibility spellings now match;
   characters unknown to an older destination Unicode database remain preserved as
   text but cannot become searchable letters under those older rules.
5. Restart all readers against the new root and runtime only after acceptance. Keep
   the old root/backup intact. Before resuming writes, rollback can stop the new
   service and restore the old executable with the old root. After new writes,
   reverting to the old backup would discard them; there is no v2-to-v1 in-place
   downgrade. A v2 Unicode-runtime switch uses another fresh offline rebuild.

A failed rebuild can leave an incomplete destination. Keep it offline for diagnosis;
choose another fresh destination for a complete retry. Success is not resumable by
reusing a partial root. When the source has corrupt/missing current text, use a
coherent backup or authoritative corpus plus its complete ACL/group configuration;
this tool cannot reconstruct missing data or invent permissions.

This same fresh-root rebuild, using a known v2 source identity, is the supported
offline compaction path. Its golden fixtures cover v1 obsolete/deleted rows, private
documents and group memberships, plus a UCD16 character under both interpreters.

## Owned demonstration output

`clean-demo --output /absolute/path` requires an Atlas marker and known output
files/state. It refuses symlink paths, filesystem roots, unowned nonempty directories
and unexpected files. It is not a general index cleanup or garbage-collection tool.
Run it before repeating a demonstration at the same output location.
