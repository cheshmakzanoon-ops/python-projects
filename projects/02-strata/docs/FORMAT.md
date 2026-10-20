# Persistent formats and recovery choices

All integers in binary structures are unsigned and big-endian. CRC32 detects
accidental corruption; it is not authentication. The source directory must have
one cooperative owner and no external writer. Keys and values are arbitrary
bytes, including empty values and byte strings resembling format headers.

## Version inventory

| Structure | Identifier | Read support | New writes |
| --- | --- | --- | --- |
| WAL transaction | `STW1` | Legacy, with conservative torn-tail handling | No |
| WAL transaction | `STW2` | Header and payload checksums | Yes |
| SSTable | `STRATAS1` | Version 1 | Version 1 |
| Manifest/backup metadata | `STRATAM1` | Version 1 | Version 1 |

Frame versions are independent of the table and manifest versions. A log can
contain a complete legacy prefix followed by v2 frames. Existing valid files are
not rewritten merely because they were opened. A successful flush rotates the
log to an empty file after the manifest checkpoint is durable.

## Record payload

| Field | Bytes | Meaning |
| --- | ---: | --- |
| commit sequence | 8 | Nonzero transaction sequence |
| kind | 1 | 1 = value, 0 = deletion |
| key length | 2 | At most 4,096 bytes |
| value length | 4 | At most 1,048,576 bytes; zero for deletion |
| key | variable | Exact user bytes |
| value | variable | Exact value bytes; empty is distinct from deletion |

A payload concatenates records and is limited to 16 MiB. A WAL transaction must
have one sequence and distinct keys; committed frames have consecutive sequences.
The first replayed sequence after checkpoint `c` must be `c + 1`. SSTable records
sort by key ascending, then sequence descending. Parsers reject invalid sizes
before allocating a claimed body.

## WAL v2

| Offset | Bytes | Meaning |
| ---: | ---: | --- |
| 0 | 4 | `STW2` |
| 4 | 4 | Payload length |
| 8 | 4 | CRC32 of payload |
| 12 | 4 | CRC32 of the preceding 12 header bytes |
| 16 | variable | Complete record payload |

The independent header checksum is essential. With a validated header, a short
payload is an incomplete final append, so recovery can preserve the complete
prefix without interpreting user values as framing. A full header with a bad
checksum, a complete payload with a bad checksum, invalid record structure, or a
sequence discontinuity fails closed. Recovery never searches inside a v2 value
for a later frame. The extra header cost is four bytes per transaction compared
with v1.

A final short header is repairable only when its available magic bytes match a
supported identifier. A complete but damaged final frame is not silently dropped.
That may require restoring a backup even when the damaged call was never
acknowledged; preserving evidence is preferable to guessing which data mattered.

## Legacy WAL v1

V1 is `STW1`, payload length, payload CRC32, then the same record payload, with a
12-byte header. Its length lacks independent protection. A short claimed payload
can mean a torn append or a damaged length hiding later frames. The reader refuses
the latter when the remaining bytes contain a complete checksummed supported
frame. Arbitrary v1 values can contain exactly that byte pattern, making some
torn tails fundamentally ambiguous. Those files remain unchanged and require an
operator decision; the new reader does not guess away potentially committed data.

New writes use v2 to remove that ambiguity for future transactions. Old binaries
refuse a live `STW2` frame. A new-engine backup or fully flushed, closed database
uses unchanged v1 tables/metadata and an empty WAL, so it can be transferred to an
older implementation after explicit compatibility checks. Never alternate old
and new writers against an active directory. The frozen
`tests/fixtures/legacy-v1.json` was produced by source
`39d3a8d4be3e8e2e7de85379790d68f5367d6825`; it includes a table, unflushed v1
transactions, and an independently written legacy backup. Tests read, continue,
export, and restore those exact bytes.

## Recovery plan before mutation

Physical scanning validates the complete prefix and records its byte boundary,
all complete batches, and a file signature (device, inode, size, modification and
change timestamps). It neither changes the descriptor position nor truncates
anything. The database then validates replay against its already validated
manifest checkpoint. Only an accepted plan can repair a suffix. A changed file
signature invalidates the plan before truncation.

This order matters when a log has both a missing transaction and a torn tail.
Repairing the tail first destroys diagnostic bytes even though open ultimately
rejects the sequence gap. Planning and application are separate operations so a
physical reader cannot make that logical decision prematurely. A completed repair
is synchronized before new appends. File signatures supplement the owner lock;
they are not a defense against a hostile actor rewriting files and timestamps.

## SSTable

An eight-byte `STRATAS1` header precedes data blocks. Each block is a four-byte
payload length, four-byte CRC32, and encoded sorted records. Blocks target 64 KiB;
a permitted single record can exceed that target, but not the 16 MiB payload cap.
One key's versions can span many blocks.

The trailing checksummed JSON index records contiguous block offsets, lengths,
first/last key hex strings, and a persistent Bloom filter. A 16-byte trailer stores
the eight-byte index offset followed by `STEND001`. Index and block payloads are
limited to 16 MiB. Open checks index coverage; record scans check complete global
order, indexed key bounds, and sequence validity. Empty tables are valid.

Bloom filters use approximately ten bits per distinct key and seven probes.
BLAKE2b-128 with personalization `strata-bloom-v1` supplies two big-endian halves;
the second half is forced odd, and probe `i` uses `(first + i * delta) % bit_count`.
The hash is stable across processes; Python's randomized `hash()` is never part of
the format. These filters accelerate absence checks and do not authorize dropping
a record from a validated table.

## Manifest and backup envelopes

Metadata is `STRATAM1`, a four-byte JSON length, four-byte CRC32, and UTF-8 JSON.
Writers emit sorted compact JSON; envelope payloads are limited to 64 MiB.
`MANIFEST` binds format 1, the unsigned checkpoint sequence, and unique
`table-<32 lowercase hex>.sst` basenames. Paths cannot escape the database.

Publication writes and synchronizes a pending file, replaces the live manifest,
and synchronizes the directory before retiring sources. The initial empty WAL is
synchronized before the first manifest. Once a manifest exists, a missing WAL is
file loss, even if the last flush left it empty. Interrupted initial creation can
resume only with an empty WAL, optional pending manifest, and owner-lock file.

`BACKUP` requires exactly format 1, original source sequence, live record count,
and a lowercase SHA-256 content digest. The digest covers sorted rows as
`key_length:u32, key, value_length:u32, value`. Restore checks that complete view
before creating a new directory. Each export rebatches values into new commit
sequences; the source sequence is provenance for that export, not a promise to
recreate the original commit history.

## Information not persisted

In-memory snapshots and transactions do not survive process death. No independent
commit-end marker records the last acknowledged WAL offset, so removal of a whole
final transaction can resemble an earlier valid log state during offline open.
Online verification can compare against the currently published memtable; an
offline reader cannot reconstruct missing history from absent bytes. Fsync,
checksums, and process-kill tests do not establish behavior for every filesystem,
controller, collision, adversarial mutation, or hardware power-loss failure.
