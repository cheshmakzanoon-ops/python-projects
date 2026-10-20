# Operating Strata

Use Linux and a local writable POSIX filesystem. All commands below run from
`projects/02-strata`. Pin uv 0.12.23 and install with
`uv sync --locked --python 3.14.8`; Python 3.13.16 is also supported. Do not place
unrelated files or symlinks inside a database directory. Strata owns its manifest,
WAL, lock, tables, and pending files.

## Transaction and snapshot use

This example demonstrates repeatable reads, a real write conflict, maintenance,
and a historical export. Choose new paths before running it:

```sh
uv run --locked python - <<'PYTHON'
from pathlib import Path
from tempfile import TemporaryDirectory
from pp_strata import Conflict, Database

with TemporaryDirectory(prefix="strata-example-") as work:
    root = Path(work)
    with Database.open(root / "database") as db:
        with db.begin() as tx:
            tx.put(b"account", b"100")
        with db.snapshot() as old:
            stale = db.begin()
            with db.begin() as winner:
                winner.put(b"account", b"120")
            stale.put(b"account", b"90")
            try:
                stale.commit()
            except Conflict:
                pass
            else:
                raise AssertionError("stale write was accepted")
            db.compact()
            assert old.get(b"account") == b"100"
            db.backup(root / "backup", snapshot=old)
        db.verify()
    Database.restore(root / "backup", root / "restored")
    with Database.open(root / "restored") as db, db.snapshot() as snapshot:
        assert list(snapshot.scan()) == [(b"account", b"100")]
PYTHON
```

Retry a conflict by restarting the entire application transaction against a new
snapshot, including its reads. An empty transaction consumes no new sequence.
A successful context exit commits; an exception aborts. Close every snapshot and
transaction promptly. There is no automatic transaction timeout; an old pin can
retain versions and deleted-key conflict metadata indefinitely.

## Inspect, verify, and maintain

```sh
uv run --locked python -m pp_strata.cli inspect /absolute/database
uv run --locked python -m pp_strata.cli verify /absolute/database
uv run --locked python -m pp_strata.cli compact /absolute/database
```

Each CLI command obtains the exclusive owner lock. Stop the application owner
first; a second owner receives `OwnerBusy`. The CLI opens the database normally,
which can repair an incomplete accepted WAL tail and remove orphan files before
running the command. Preserve a filesystem copy before investigating corruption.
The CLI is not a forensic viewer for a damaged directory.

Within an already open owner, `db.verify()` never repairs files. It reopens table
metadata/blocks without the application LRU, validates the manifest, scans the
WAL, and compares replay with the published memtable. A checksum or read I/O error
poisons the writer. Verification cannot bypass the filesystem cache or prove a
controller flushed data correctly. A failed owner must be recovered before this
audit runs, because its WAL and published memtable can legitimately differ after
an uncertain commit. `internal_records` counts persisted versions
and current memtable records, not just visible user keys.

`inspect()` reports current/checkpoint sequences, active/oldest pins,
`conflict_heads`, memtable record count, tables, disk bytes, and per-owner I/O/cache
counters. Rising heads during delete-heavy churn usually mean an old pin remains.
After those handles close, full compaction can reclaim obsolete deleted heads.
Scans and compaction hold the publication mutex; investigate long operations
before increasing writer concurrency. Full compaction rewrites the entire live
set and can stall commits.

## Respond to uncertain writes or corruption

`WriterFailed` means further writes and maintenance are refused until close and
successful recovery. Already published snapshots may remain readable. Do not
convert the original I/O error into an application success, and do not assume the
transaction rolled back: a complete unacknowledged batch can survive. Use a
stable application operation ID when deciding whether to retry an external
business action.

On `Corruption`, preserve the complete directory before any repair attempt. Do
not manufacture an empty WAL, edit checksums, or delete an unexpected table to
force open. Missing log records and file loss require a validated backup or a
separately reviewed reconstruction. A v1 torn tail containing frame-shaped value
bytes can be ambiguous; refusal preserves those bytes rather than guessing which
transactions were committed. [FORMAT.md](FORMAT.md) explains the distinction.

When open succeeds, v2 writes can follow a complete v1 prefix. No table migration
is needed. Old binaries refuse a live v2 log. For an explicitly checked transfer
to an old implementation, use a logical backup or complete a successful flush
and close so the log is empty. Never switch binaries while an owner is running.
A legacy initialization interrupted after creating a manifest but before creating
its WAL is refused because that state cannot be distinguished safely from log
loss.

## Back up and restore

```sh
uv run --locked python -m pp_strata.cli backup /absolute/database /absolute/new-backup
uv run --locked python -m pp_strata.cli restore /absolute/new-backup /absolute/new-restored
```

Backup refuses existing destinations and destinations inside the source database.
The library can export an old retained view with
`db.backup(new_path, snapshot=old_snapshot)`. It captures immutable rows before
destination I/O; the source can continue writing or close after that capture.
The final `BACKUP` digest is published only after the new database is complete.
A failure preserves the partial destination for diagnosis; retry to another new
path. Restore validates the entire live content and never replaces a directory.

An export stores values, not original transaction history or physical tables.
Commit sequences are rebased during every export. `source_sequence` identifies
that export's input view; do not treat it as a restored transaction-number
contract. Backups are neither encrypted nor authenticated. Treat the digest as a
corruption check and preserve trusted provenance separately.

## Demonstration output ownership

```sh
uv run --locked python -m pp_strata.cli demo --output /tmp/strata-demo --seed 1729
uv run --locked python -m pp_strata.cli clean-demo --output /tmp/strata-demo
```

Use a new absolute directory. Nonempty unmarked output is refused. Cleanup checks
the exact Strata marker and removes its fixed owned child files/subtrees; unrelated
direct children survive. Owned subtrees belong entirely to the demo, so do not
put personal data inside them. Symlink roots/directly owned children are refused.
Generated databases and reports belong outside tracked source.

## Validation and resource limits

Run normal checks with `python scripts/portfolio.py check strata` from the
repository root. Set `PORTFOLIO_PYTHON` explicitly and use a separate environment
for 3.13.16. Run interpreter builds sequentially because they share `dist/`.

The default suite includes overlapping transaction histories, a dictionary oracle,
retention properties, process-exit faults, publication errors, descriptor release,
legacy storage fixtures, backup lifetime, and deterministic hot-version I/O bounds.
[The benchmark guide](BENCHMARKS.md) separates the small five-repeat version-seek
workload from the costly standard and extended suites. Run heavy workloads alone.

Scans, transaction overlays, and backups materialize results. The memtable target
is encoded bytes, not a strict resident-memory limit. Table creation also holds
unique keys for its Bloom filter and metadata for the sparse index. Index/Bloom
format limits can cap a full-compaction output. Large datasets, very old pins,
and a full-rewrite policy require measuring actual memory, I/O, and pause time;
there is no automatic disk-space reserve or background maintenance scheduler.
