# Storage architecture

Strata has one owning process per database directory. A `Database` coordinates a
commit sequence, ordered in-memory records, immutable table files, a WAL, active
snapshot pins, and write-conflict heads. The implementation deliberately keeps
commit publication and maintenance synchronous under one reentrant mutex. It
provides snapshot isolation, not serializable transactions or concurrent
multi-process readers.

## Responsibilities and ownership

| Component | Owns | Does not decide |
| --- | --- | --- |
| `api.py` | Process lock, transaction admission, publication, pins, live descriptor set, backup coordination | Binary framing and skip-list topology |
| `memtable/` | Ordered `(key, -sequence)` records and encoded-size accounting | Commit durability or conflict policy |
| `wal/frames.py` | Versioned frames, read-only recovery plans, explicit tail repair, log replacement | Which checkpoint is authoritative |
| `sstable.py` | Checksummed blocks, sparse ranges, Bloom filter, LRU and point seeks | Which versions snapshots still need |
| `compaction.py` | Pure one-pass version retention and conflict-head reclamation | File creation or manifest publication |
| `io.py` | Complete writes, durable directory creation, atomic metadata envelopes | Application retry decisions |

The owner holds `fcntl.flock` until WAL/table release has been attempted. Every
owning handle also records its process ID; inherited handles are rejected after
`fork`. Storage descriptors belong to the database, never a snapshot. Independent
handles may be used by different threads. A transaction or snapshot itself should
not be mutated or closed concurrently by multiple callers.

## Transaction timeline

A transaction pins the current committed sequence when `begin()` runs. Its reads
use that sequence plus one final private mutation per key. Repeated puts replace
the private value, and private deletes hide committed values. No buffered write
is shared with another transaction. A normal context exit commits; an exception
aborts. Explicit commit or abort closes the handle and releases its pin.

Under the publication mutex, commit performs:

1. Reject a closed/inherited/failed owner and compare every written key's latest
   change sequence against the transaction's starting sequence.
2. Validate the complete encoded batch before touching the WAL. Empty writes do
   not consume a sequence; a nonempty batch receives `current_sequence + 1`.
3. Append one complete transaction frame and synchronize it in `sync` mode.
4. Add all records, update conflict heads, and publish the new committed sequence.
5. Flush if the encoded memtable threshold has been reached, then acknowledge.

The lock prevents another reader from observing the middle of publication. A
published batch and an acknowledged call are different events: a synchronization,
publication, or automatic-flush error may leave a whole transaction that the
caller never acknowledged. Any uncertain storage error poisons further writes.
Recovery resolves the file state; application operation IDs resolve business
retry ambiguity. `flush` durability omits WAL synchronization and has a weaker
power-loss contract.

First-committer-wins checks the write set, including a key inserted and deleted
since an old transaction began. It does not validate reads or predicates. Two
transactions reading different doctors as on-call can each turn one off; that
write skew is permitted. The acceptance tests demonstrate it explicitly.

## Snapshot visibility and lookup work

For a key and snapshot sequence `s`, select the highest committed sequence
`<= s`. A selected tombstone means absence, while `b""` is an ordinary value.
Point lookup applies that rule across the memtable and every live table.

The skip-list seeks the full internal key `(user_key, -s)`. Seeking only the
beginning of a user-key run would scan every newer version before reaching an
old snapshot. SSTable lookup first bounds candidate blocks by user-key ranges.
The usual newest-value lookup reads its first candidate block. If that block
contains only newer versions, a binary search over terminal internal keys skips
blocks until the first potentially visible version, then a binary search locates
the record inside that block. A hot key spanning `B` blocks needs logarithmic
block probes rather than a scan of all newer versions.

Range scans merge ordered streams, choose one visible version per key, and omit
tombstones. They materialize byte tuples under the mutex before returning an
iterator. An iterator therefore survives snapshot closure and table retirement;
it does not retain descriptors. This trades memory proportional to the result
and a blocking critical section for simple, explicit lifetime ownership.
Transaction scans additionally construct and sort their private overlay.

## Retention, deletion, and conflict memory

Let `f` be the oldest pinned sequence, or the current sequence when there are no
pins. Full compaction consumes records in key/descending-sequence order and
retains every version above `f`, plus the newest version at or below `f` for each
key. That floor version answers every pinned view at or above `f`. With no pins,
a latest tombstone can be omitted because compaction covers the entire live file
set; no excluded older table can resurrect its value.

Conflict heads have a different purpose from retained values. Live keys always
keep their latest sequence. A deleted key needs a head only while a handle older
than that deletion remains pinned. Once every handle starts at or after the
change, its head can be reclaimed even if a conservative retained tombstone
remains. The retention pass constructs the next head map alongside table output;
the owner installs it only after the new manifest is durable. `inspect()` exposes
`conflict_heads` so churn and long-lived pins are observable. Read-only pins are
conservatively included in this floor, avoiding a second lifetime registry.

## File publication and retirement

Flush writes an exclusive UUID-named table, synchronizes its contents and parent
directory, then atomically replaces and synchronizes the manifest. Only then does
the owner install the table, clear the memtable, and replace the WAL with a synced
empty file. The checkpoint makes old log frames redundant even if a crash leaves
the pre-rotation WAL.

Compaction uses the same manifest boundary before switching the in-memory table
set. Every retired descriptor is scheduled for release before any release runs;
a close error cannot abandon the rest. Old filenames are unlinked only after
manifest synchronization and descriptor release. An error leaves the owner
failed and old files available for recovery or diagnosis. Reopening follows the
authoritative manifest and cleans orphan tables only after successful recovery.

## Recovery and verification

Open validates the manifest and every referenced table, then scans the WAL
without mutation. Its `RecoveryPlan` identifies complete frames and a possible
incomplete suffix. The database checks consecutive replay against the manifest
checkpoint before permitting tail repair. A rejected logical plan leaves even a
torn suffix intact. Applying an accepted plan checks the file signature again,
truncates only the incomplete suffix, synchronizes that repair, and positions the
log for appends. See [the format contract](FORMAT.md) for legacy ambiguity and
upgrade rules.

`verify()` audits newly opened manifest/table/WAL structures, bypassing the
application block cache. It compares replayed WAL records with the published
memtable and checks table bounds, ordering, checksums, sequences and Bloom
membership. It never repairs a log. Detected corruption or read I/O failure
poisons writes; cached published reads may remain available. This audits bytes
returned by the filesystem, not the storage controller's honesty or every possible
power-loss outcome.

## Backup lifetime

Backup captures one complete logical view under the mutex, then releases the
source lock before writing a new database. The captured immutable rows outlive
source compaction, snapshot closure, and owner shutdown. Destination commits are
byte-bounded; the new database is compacted before its `BACKUP` content digest is
published. Restore validates the export schema and complete live-content hash
before creating a destination. Exports retain values, not original transaction
boundaries or commit numbers. Both backup and scans materialize results; they are
not streaming exports for datasets larger than available memory.
