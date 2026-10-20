# Design decisions

## One owner and one publication mutex

A file lock prevents two cooperative owners, and a PID check rejects inherited
handles after `fork`. Within one process, a mutex serializes commit publication,
scans, and maintenance. This makes batch visibility, snapshot pin lifetimes, and
file retirement share one ordering boundary. The cost is blocking: a long scan or
full compaction delays commits. Background compaction or independent readers
would require descriptor/version reference counting and a more involved manifest
installation protocol. They should follow a measured latency requirement rather
than precede one.

## Snapshot isolation and first-committer-wins

Read sets and range predicates are deliberately absent from conflict detection.
The engine rejects a written key changed since transaction start, including an
insert/delete cycle, while preserving repeatable reads and private overlays.
This is less restrictive than serializability and permits write skew. Applications
requiring cross-key invariants need a common written guard key or coordination
above the engine; calling the isolation serializable would conceal that choice.

Conflict metadata must preserve a change even after its value is deleted. Keeping
every head forever was correct but leaked memory with process-lifetime churn.
Compaction now retains live heads and deleted heads newer than the oldest pinned
sequence. Older deleted heads cannot invalidate any remaining transaction, so
they can be reclaimed. Read-only pins conservatively participate in that floor,
keeping one lifetime registry and a straightforward proof. Property tests compare
every retained view with complete dictionary histories and check the exact heads
needed by overlapping transactions.

## Full compaction over a partitioned level policy

Compacting the whole live file set makes tombstone removal provable: no excluded
older table can reveal a deleted value afterward. Retain every version newer than
the oldest snapshot and one floor version. A long-lived snapshot can therefore
retain substantial history. Full rewrites stall writers and amplify I/O; this is
a deliberate limit rather than a production LSM throughput claim. Leveled or
incremental compaction would need per-range overlap proofs before it could drop
those tombstones safely.

LevelDB's SSTable/manifest architecture informed this design, while Strata's
storage implementation is independent. See its
[implementation notes](https://github.com/google/leveldb/blob/main/doc/impl.md).
SQLite is an explicitly configured benchmark baseline, not Strata's backend.

## Compound-key seeks instead of scanning newer versions

A user-key-only seek looks efficient for recent values but becomes linear in the
version count for an old snapshot. The skip-list now seeks `(key, -sequence)`.
SSTables retain their existing on-disk index: candidate user-key ranges bound the
search, and decoded terminal internal keys guide a binary search among blocks.
The first candidate block remains a fast path for current reads. This improves
hot historical lookup without a table-format migration or a larger persistent
index. The tradeoff is a few block probes for an old view, while scans still read
the complete requested range. Deterministic I/O-bound tests and the small
[version-seek workload](BENCHMARKS.md#hot-version-point-reads) exercise this case.

## Checksummed v2 WAL headers

V1 protected payloads but not their declared length. Searching a short payload
for later valid frame magic confused arbitrary user bytes with transaction
boundaries. A real process-exit regression reproduces an acknowledged-prefix
recovery failure with a frame-shaped value. V2 adds an independent header CRC so
recovery can trust a checked length before deciding a final payload is incomplete.
It never scans opaque v2 values for framing. The cost is four bytes per batch.

The reader accepts complete v1 and v2 frames together; new appends are v2. Legacy
ambiguous tails remain refused rather than being reinterpreted destructively.
[FORMAT.md](FORMAT.md) defines upgrade, export, and old-reader behavior. CRC32 is
an accidental-corruption check, not an adversarial integrity protocol.

## Plan recovery before repairing files

A physical scanner knows frame boundaries but not the authoritative checkpoint.
It now returns a read-only plan. The owner validates sequence replay against the
manifest before authorizing truncation, then verifies the file signature again.
This prevents a failed open from discarding a torn suffix before discovering a
missing complete transaction. It also gives verification a nonmutating parser.
A plan is not a durable commit record; a crash during an accepted repair can
require repeating recovery, but cannot remove a complete accepted prefix.

## Verification bypasses the application cache

A successful cached read proves what was loaded, not what persistent files now
contain. `verify()` reopens table metadata and blocks without the application
LRU, scans the current WAL without repair, and compares it with the published
memtable. It also checks that the persisted manifest matches the installed file
set. Detected corruption or read I/O failure poisons writes. Cached previously
published reads can remain useful for diagnosis, but the engine must not compact
away evidence while presenting a healthy writer. The filesystem's own cache and
hardware remain outside this diagnostic guarantee.

## Explicit uncertain outcomes and cleanup ownership

Sync acknowledgement follows a complete WAL write and `fsync`; automatic
maintenance can still fail afterward. An exception never claims rollback of an
already durable batch. The owner enters a failed state until close and recovery,
and the application decides how to retry an idempotent operation. Hiding such an
error or continuing to write would make sequence and durability claims unreliable.

Every table scheduled for retirement is registered for release before releases
begin. A close error therefore cannot leak the remaining descriptors, and orphan
files remain available if cleanup does not finish. Source deletion stays after
durable manifest publication. Retrying a failed POSIX close blindly is avoided:
a descriptor may already have been released and reused.

## Materialized snapshots and logical exports

Scans return detached byte tuples. Backup captures a complete view under the
mutex and writes it after releasing the source, so it can finish even after the
source snapshot and database close. This is simpler than streaming while pinning
files or retaining an owner lock through all destination I/O. It consumes memory
proportional to the result and is unsuitable for unbounded scans. A backup stores
live values and a content digest, not physical table history or original commit
boundaries. Restore rebatches into new sequences and validates content before
creating its destination. Backups are neither encrypted nor authenticated.
