# Formats and decisions

## Version-one persisted formats

All integers use network byte order. Keys are bytes (including empty keys), up
to 4 KiB; values are bytes (including empty values), up to 1 MiB. A mutation
record is `u64 sequence, u8 kind, u16 key_length, u32 value_length, key, value`.
Kind 0 is a tombstone with zero value length; kind 1 is a byte value. Sequence
zero is reserved. Encoded batches are limited to 16 MiB. Lengths are checked
before body slicing or bounded reads. CRC32 detects accidental corruption;
it is not authentication against an adversary who can rewrite the database.

WAL frames are `STW1, u32 payload_length, u32 CRC32(payload), payload`.
One frame contains one nonempty transaction, one sequence, and unique user keys.
Recovery requires strictly increasing frame sequences. Only an incomplete final
frame is truncated and synced. Invalid magic, oversized lengths, complete
checksum failures, duplicates, and nonmonotonic sequences fail closed. When an
incomplete claimed length covers a later valid frame, recovery reports interior
corruption instead of hiding later data. A maliciously changed incomplete length
without a detectable later frame cannot always be distinguished from a real
torn tail; CRC and frame magic are corruption checks, not an adversarial MAC.

SSTables start with `STRATAS1`; data blocks are `u32 length, u32 CRC, records`.
The final checksummed JSON index contains complete block offsets, sizes, key
ranges (hex), and Bloom bits (hex). An ending `u64 index_offset, STEND001`
locates it. Indexes and blocks are bounded to 16 MiB. Empty tables are valid.
Versions of one hot key may span blocks; sparse lookup deliberately seeks back
through overlapping key ranges. The stable Bloom hash is BLAKE2b-128 with
personalization `strata-bloom-v1`; two big-endian halves use double hashing,
with the second half forced odd. Fixed record/hash vectors pin this format.

The manifest is `STRATAM1, u32 length, u32 CRC, canonical JSON`, bounded to
64 MiB. It records format 1, the checkpoint sequence, and a unique list of
`table-<32 lowercase hex>.sst` basenames. Unsupported versions fail explicitly;
there is no automatic migration. A future version must use a separately tested
converter or export/import through byte records. Backups use the same metadata
envelope and a length-delimited SHA-256 digest over sorted live key/value rows.
Their version-one schema requires exactly `format`, `source_sequence`, `records`,
and `content_sha256`: version is integer 1, source sequence is an unsigned 64-bit
integer, record count is a nonnegative integer, and digest is 64 lowercase hex
characters. Booleans are not integers for this boundary. Restore validates this
schema before opening/recovering the source or creating destination state.

## Publication and uncertainty

Sync commits append the complete batch, call `fsync(WAL)`, then publish records
and the sequence under a mutex. `durability="flush"` omits WAL fsync and offers
process-crash testing only, with no power-loss durability guarantee. Short writes
are completed in a loop; a zero write is an error. Any append/sync/publication
exception poisons the writer. A complete unacknowledged frame may be recovered.
An incomplete attempted frame has no committed sequence. All recovered complete
sequences, acknowledged or not, advance the next sequence; checkpoint sequences
remain monotonic even after all records are deleted and compacted away.

Maintenance writes an exclusive UUID table, syncs the table and directory, writes
and syncs a pending manifest, replaces the live manifest, syncs its directory,
then retires source files. A flush subsequently replaces the WAL with a synced
empty file. Old WAL frames at/below the checkpoint are validated and skipped.
Failure during automatic maintenance can raise after a whole batch has already
published; it remains an unacknowledged but potentially committed transaction.
Reads expose the last fully published sequence until recovery resolves disk
state. Errors are never converted into successful acknowledgements.
Creating a new database hierarchy also syncs each newly created directory's
parent entry, walking from the previously existing ancestor down. Syncing only
the final database directory would leave its own creation outside that boundary.

This assumes a local POSIX filesystem with truthful fsync/rename behavior, one
owner, no external mutation, and functioning storage. Process-kill tests cannot
establish behavior under every power loss, filesystem, controller, or hardware
fault. Network filesystems and Windows durability are unsupported.

## Alternatives and boundaries

LevelDB's LSM/SSTable/manifest design influenced the architecture; this is an
original deliberately smaller implementation ([design reference](https://github.com/google/leveldb/blob/main/doc/impl.md)).
SQLite is a benchmark baseline, never the storage implementation. A full
compaction policy favors a reviewable correctness boundary over leveled
throughput. No WAL compression, block compression, SQL, distributed protocol,
multi-process readers, or background compaction is implemented. Scans and backup
materialize rows; live-key conflict heads use memory proportional to keys edited
in the owning process. A long-lived snapshot can grow retained storage.
