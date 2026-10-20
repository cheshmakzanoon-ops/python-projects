# Architecture

`api.py` owns the process lock, publication mutex, monotonic committed sequence,
snapshot pins, conflict heads, and live table descriptors. `Transaction` buffers
one final mutation per key. Get and ordered half-open scans overlay that private
set over the transaction's original snapshot. A successful context exit commits;
an exceptional exit aborts. Explicit commit or abort closes the handle.

```mermaid
flowchart LR
    T[Private transaction] --> C[Validate size and write conflicts]
    C --> W[Append complete CRC WAL batch]
    W --> S[fsync in sync mode]
    S --> P[Publish all records and sequence under mutex]
    P --> M[Ordered skip-list]
    M --> F[Write checksummed SSTable and sync]
    F --> V[Replace and sync manifest]
    V --> R[Rotate WAL / retire obsolete files]
```

Readers hold a commit sequence. Point lookups choose the newest record at or
below it across memtable and immutable tables. A tombstone is a visible absence.
Scans merge ordered record streams with `heapq.merge`, pick one visible version
per key, and remove tombstones. Each scan materializes immutable byte tuples
under the publication lock. Iterators therefore survive file retirement without
retaining descriptors. This deliberate memory/latency tradeoff avoids dangling
file references. Very large scans consume memory proportional to their result.

The memtable is an original 20-level deterministic skip-list ordered by user key
then descending sequence. Stable BLAKE2b-derived node heights keep insertion
expected logarithmic without process-random on-disk behavior. It tracks encoded
bytes and flushes at an 8 MiB default. One oversized allowed record may exceed
the 64 KiB block target, but never the 16 MiB parser bound.

SSTables stream records into approximately 64 KiB CRC blocks. A checksummed
footer describes every block's byte bounds and first/last keys and stores a
10-bit-per-key, seven-probe Bloom filter. A 32-block LRU cache per table is
configurable down to zero. Point lookup seeks via the sparse index, walks back
over any blocks sharing the key, and reads only candidate blocks. Each accessed
block validates its checksum and ordering. Open checks all blocks, sequence
bounds, and Bloom membership while reconstructing conflict heads.

First-committer-wins compares every written key's latest sequence with the
transaction sequence. Conflict heads survive deletion and in-process tombstone
removal. On reopen there are no surviving transactions; heads reconstructed from
retained records suffice. Reads do not enter the conflict set, which permits
documented write skew.

Compaction merges the complete live file set. It retains every version newer
than the oldest pinned sequence and the newest version at or below that floor.
Without pins it retains only the latest live value; a latest tombstone can be
removed because no excluded older table exists. The manifest is synced before
old descriptors close and files unlink. Recovery follows exactly the manifest,
replays later complete WAL frames, and removes orphan table/pending files.
The WAL must exist once the first manifest has been published. Consecutive
transaction sequences connect replay to the manifest checkpoint; a missing
prefix or interior frame fails as corruption rather than hiding lost writes.
The initial empty WAL is synchronized before the first manifest, allowing safe
retries after interrupted initialization without recreating a lost log.

Backup materializes one consistent snapshot, writes bounded durable batches into
a new independent database directory, compacts it, and records a content hash.
Restore validates the content digest before creating a new destination.

Failure boundaries: `fcntl.flock` rejects a second owning handle/process. A PID
check rejects inherited handles after fork. Independent handles are thread safe;
do not mutate or close the same transaction/snapshot concurrently. Unknown I/O
outcomes poison all writes until close/recovery. Previously published snapshots
remain available. No in-memory handle survives process termination.
