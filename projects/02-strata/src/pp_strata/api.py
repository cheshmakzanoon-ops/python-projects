"""Single-process MVCC publication, compaction, consistent backup, and recovery."""

from __future__ import annotations

import fcntl
import hashlib
import heapq
import os
import re
import threading
import uuid
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from pp_strata.codec.records import MAX_BATCH, Record, encode, validate
from pp_strata.compaction import VersionRetention
from pp_strata.errors import Closed, Conflict, Corruption, OwnerBusy, WriterFailed
from pp_strata.io import (
    Failpoint,
    atomic_metadata,
    durable_mkdir,
    noop,
    read_metadata,
    sync_directory,
)
from pp_strata.memtable import Memtable
from pp_strata.sstable import Table, create_table
from pp_strata.wal.frames import WAL

TABLE_NAME = re.compile(r"table-[0-9a-f]{32}\.sst\Z")


class Database:
    """One owner, many snapshot handles; commits serialize under a reentrant lock.

    Successful transaction context exit commits; exceptional exit aborts. Sync
    acknowledgement follows fsync(WAL). An uncertain I/O error poisons writes;
    existing snapshots remain readable until close. Reopen resolves ambiguity.
    """

    @classmethod
    def open(
        cls,
        path: str | Path,
        *,
        durability: Literal["sync", "flush"] = "sync",
        failpoint: Failpoint = noop,
        memtable_bytes: int = 8 * 1024 * 1024,
        cache_blocks: int = 32,
    ) -> Self:
        return cls(Path(path), durability, failpoint, memtable_bytes, cache_blocks)

    def __init__(
        self,
        path: Path,
        durability: str,
        failpoint: Failpoint,
        memtable_bytes: int,
        cache_blocks: int,
    ) -> None:
        if durability not in ("sync", "flush") or memtable_bytes < 1024 or cache_blocks < 0:
            raise ValueError("invalid durability, memtable, or cache configuration")
        self.path = path.resolve()
        durable_mkdir(self.path)
        if any(p.is_symlink() for p in self.path.iterdir()):
            raise Corruption("database directory must not contain symbolic links")
        self._lock = threading.RLock()
        self._owner_pid = os.getpid()
        self._closed = False
        self._failed = False
        self._sequence = 0
        self._checkpoint = 0
        self._pins: Counter[int] = Counter()
        self._latest: dict[bytes, int] = {}
        self._tables: list[Table] = []
        self._memtable = Memtable()
        self._durability = durability
        self._failpoint = failpoint
        self._memtable_bytes = memtable_bytes
        self._cache_blocks = cache_blocks
        self._wal_bytes = 0
        self._table_bytes_written = 0
        self._logical_bytes = 0
        self._retired_block_reads = 0
        self._retired_read_bytes = 0
        self._retired_cache_hits = 0
        self._owner_fd = os.open(self.path / "LOCK", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self._owner_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._owner_fd)
            raise OwnerBusy(f"database already owned: {self.path}") from exc
        except BaseException:
            os.close(self._owner_fd)
            raise
        wal: WAL | None = None
        try:
            manifest = self.path / "MANIFEST"
            if not manifest.exists():
                # Never initialize over an unrecognized nonempty database directory.
                if any(
                    p.name not in ("LOCK", "WAL", "MANIFEST.pending") for p in self.path.iterdir()
                ):
                    raise Corruption("missing manifest in nonempty database")
                wal_path = self.path / "WAL"
                if wal_path.exists() and wal_path.stat().st_size:
                    raise Corruption("missing manifest with nonempty WAL")
                # Establish and sync the WAL before publishing the first manifest.
                # A retry may finish this initialization only while the WAL is empty.
                # Once the manifest exists, a missing WAL is evidence of file loss.
                wal = WAL(wal_path, failpoint)
                atomic_metadata(manifest, {"format": 1, "sequence": 0, "tables": []})
            state = read_metadata(manifest)
            version, sequence, names = (
                state.get("format"),
                state.get("sequence"),
                state.get("tables"),
            )
            if (
                type(version) is not int
                or version != 1
                or type(sequence) is not int
                or not 0 <= sequence < 2**64
                or not isinstance(names, list)
                or len(names) != len(set(str(x) for x in names))
            ):
                raise Corruption("invalid manifest schema")
            self._sequence = self._checkpoint = sequence
            for name in names:
                if not isinstance(name, str) or not TABLE_NAME.fullmatch(name):
                    raise Corruption("invalid manifest table path")
                table = Table(self.path / name, cache_blocks)
                self._tables.append(table)
                for record in table.records():
                    if record.sequence > sequence or not table.bloom.contains(record.key):
                        raise Corruption("table sequence or Bloom disagrees with manifest")
                    self._latest[record.key] = max(self._latest.get(record.key, 0), record.sequence)
            if wal is None:
                try:
                    wal = WAL(self.path / "WAL", failpoint, create=False)
                except FileNotFoundError as exc:
                    raise Corruption("missing WAL in initialized database") from exc
            plan = wal.scan()
            replay = plan.replay_after(self._checkpoint)
            wal.apply_recovery(plan)
            for batch in replay:
                self._publish(batch)
            self._wal = wal
            self._cleanup_orphans()
        except BaseException:
            with ExitStack() as cleanup:
                cleanup.callback(os.close, self._owner_fd)
                for table in self._tables:
                    cleanup.callback(table.close)
                if wal is not None:
                    cleanup.callback(wal.close)
            raise

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def writer_failed(self) -> bool:
        return self._failed

    def _check(self, write: bool = False) -> None:
        if self._closed or os.getpid() != self._owner_pid:
            raise Closed("database closed or inherited across fork; open a new owner")
        if write and self._failed:
            raise WriterFailed("persistence state uncertain; close and reopen before writing")

    def _publish(self, batch: Sequence[Record]) -> None:
        for record in batch:
            self._memtable.add(record)
            self._latest[record.key] = record.sequence
        self._sequence = batch[0].sequence

    def _cleanup_orphans(self) -> None:
        live = {table.path.name for table in self._tables}
        for path in self.path.iterdir():
            if (TABLE_NAME.fullmatch(path.name) and path.name not in live) or path.name in (
                "MANIFEST.pending",
                "WAL.pending",
            ):
                path.unlink()
        sync_directory(self.path)

    def snapshot(self) -> Snapshot:
        with self._lock:
            self._check()
            return Snapshot(self, self._sequence)

    def begin(self) -> Transaction:
        with self._lock:
            self._check(write=True)
            return Transaction(self, self._sequence)

    def _get(self, key: bytes, sequence: int) -> bytes | None:
        with self._lock:
            self._check()
            try:
                candidates = [self._memtable.get(key, sequence)]
                candidates.extend(table.get(key, sequence) for table in self._tables)
                records = [record for record in candidates if record is not None]
                return max(records, key=lambda record: record.sequence).value if records else None
            except (Corruption, OSError):
                self._failed = True
                raise

    def _records(self, start: bytes = b"", stop: bytes | None = None) -> Iterator[Record]:
        streams = [self._memtable.records(start, stop)]
        streams.extend(table.records(start, stop) for table in self._tables)
        previous: tuple[bytes, int] | None = None
        for record in heapq.merge(*streams, key=lambda record: record.order):
            if record.order != previous:
                yield record
                previous = record.order

    def _scan(self, sequence: int, start: bytes, stop: bytes | None) -> list[tuple[bytes, bytes]]:
        # Materialization pins file lifetime under the lock. Detached byte tuples
        # remain safe even if the caller closes the snapshot before iterating.
        with self._lock:
            self._check()
            try:
                result: list[tuple[bytes, bytes]] = []
                seen: bytes | None = None
                for record in self._records(start, stop):
                    if record.sequence <= sequence and record.key != seen:
                        seen = record.key
                        if record.value is not None:
                            result.append((record.key, record.value))
                return result
            except (Corruption, OSError):
                self._failed = True
                raise

    def _commit(self, tx: Transaction) -> int:
        with self._lock:
            self._check(write=True)
            if any(self._latest.get(key, 0) > tx.sequence for key in tx._writes):
                raise Conflict("write set changed after snapshot")
            if not tx._writes:
                return self._sequence
            batch = [
                Record(key, self._sequence + 1, value) for key, value in sorted(tx._writes.items())
            ]
            payload = encode(batch)  # Validate before touching persistent state.
            try:
                self._wal_bytes += self._wal.append(batch, self._durability == "sync")
                self._failpoint("before_publish")
                self._publish(batch)
                self._failpoint("after_publish")
            except BaseException:
                self._failed = True
                raise
            self._logical_bytes += len(payload)
            # Automatic maintenance failures leave the committed WAL recoverable;
            # no success is reported if maintenance makes the outcome uncertain.
            if self._memtable.bytes >= self._memtable_bytes:
                self.flush()
            return self._sequence

    def _new_table(self, records: Iterator[Record]) -> Table:
        path = self.path / f"table-{uuid.uuid4().hex}.sst"
        create_table(path, records, self._failpoint)
        self._table_bytes_written += path.stat().st_size
        return Table(path, self._cache_blocks)

    def _install(self, tables: list[Table]) -> None:
        atomic_metadata(
            self.path / "MANIFEST",
            {"format": 1, "sequence": self._sequence, "tables": [t.path.name for t in tables]},
            self._failpoint,
        )
        self._checkpoint = self._sequence

    def flush(self) -> None:
        with self._lock:
            self._check(write=True)
            if not self._memtable.count:
                return
            new: Table | None = None
            try:
                new = self._new_table(self._memtable.records())
                self._install([*self._tables, new])
                self._tables.append(new)
                self._memtable = Memtable()
                self._wal.rotate()
            except BaseException:
                self._failed = True
                if new is not None and new not in self._tables:
                    new.close()
                raise

    def compact(self) -> None:
        with self._lock:
            self._check(write=True)
            self.flush()
            if not self._tables:
                return
            oldest = min(self._pins) if self._pins else self._sequence
            retention = VersionRetention(oldest, bool(self._pins))
            new: Table | None = None
            try:
                new = self._new_table(retention.records(self._records()))
                self._install([new])
                old, self._tables = self._tables, [new]
                self._latest = retention.heads
                # Readers finish under the lock or hold detached tuples. Close
                # descriptors before cleanup can fail, so poisoned close leaks none.
                with ExitStack() as cleanup:
                    for table in old:
                        self._retired_block_reads += table.block_reads
                        self._retired_read_bytes += table.read_bytes
                        self._retired_cache_hits += table.cache_hits
                        cleanup.callback(table.close)
                self._failpoint("before_obsolete_cleanup")
                for table in old:
                    table.path.unlink()
                sync_directory(self.path)
                self._failpoint("after_obsolete_cleanup")
            except BaseException:
                self._failed = True
                if new is not None and new not in self._tables:
                    new.close()
                raise

    def inspect(self) -> dict[str, object]:
        with self._lock:
            self._check()
            return {
                "format": 1,
                "sequence": self._sequence,
                "checkpoint": self._checkpoint,
                "writer_failed": self._failed,
                "active_snapshots": sum(self._pins.values()),
                "oldest_snapshot": min(self._pins) if self._pins else None,
                "conflict_heads": len(self._latest),
                "memtable_records": self._memtable.count,
                "tables": [t.path.name for t in self._tables],
                "disk_bytes": sum(p.stat().st_size for p in self.path.iterdir() if p.is_file()),
                "wal_bytes_written": self._wal_bytes,
                "table_bytes_written": self._table_bytes_written,
                "logical_bytes_written": self._logical_bytes,
                "block_reads": self._retired_block_reads + sum(t.block_reads for t in self._tables),
                "block_read_bytes": self._retired_read_bytes
                + sum(t.read_bytes for t in self._tables),
                "cache_hits": self._retired_cache_hits + sum(t.cache_hits for t in self._tables),
            }

    def verify(self) -> dict[str, object]:
        with self._lock:
            self._check(write=True)
            try:
                return self._verify_persistent()
            except (Corruption, OSError):
                self._failed = True
                raise

    def _verify_persistent(self) -> dict[str, object]:
        """Audit fresh persisted structures; caller holds the publication mutex."""
        expected = {
            "format": 1,
            "sequence": self._checkpoint,
            "tables": [table.path.name for table in self._tables],
        }
        if read_metadata(self.path / "MANIFEST") != expected:
            raise Corruption("persistent manifest differs from installed table set")
        count = 0
        for table in self._tables:
            # Reopen metadata and blocks with no cache: successful logical
            # reads do not establish that their persistent bytes remain valid.
            fresh = Table(table.path, cache_blocks=0)
            try:
                for record in fresh.records():
                    if record.sequence > self._checkpoint or not fresh.bloom.contains(record.key):
                        raise Corruption("table sequence or Bloom disagrees with manifest")
                    count += 1
            finally:
                fresh.close()
        fresh_wal = WAL(self.path / "WAL", create=False)
        try:
            plan = fresh_wal.scan()
            if plan.discarded_bytes:
                raise Corruption("incomplete WAL tail; reopen for recovery")
            replay = plan.replay_after(self._checkpoint)
            records = sorted(
                (record for batch in replay for record in batch), key=lambda r: r.order
            )
            if records != list(self._memtable.records()):
                raise Corruption("persistent WAL differs from published memtable")
        finally:
            fresh_wal.close()
        return {
            "status": "passed",
            "internal_records": count + len(records),
            "sequence": self._sequence,
            "wal_frames": len(plan.batches),
        }

    def backup(
        self, destination: str | Path, *, snapshot: Snapshot | None = None
    ) -> dict[str, object]:
        target = Path(destination).absolute()
        if (
            target.exists()
            or target.is_symlink()
            or self.path == target.resolve()
            or self.path in target.resolve().parents
        ):
            raise ValueError("backup destination must be new and outside the source database")
        with self._lock:
            self._check()
            if snapshot is not None:
                snapshot._check()
                if snapshot._db is not self:
                    raise ValueError("snapshot belongs to another database")
            sequence = snapshot.sequence if snapshot is not None else self._sequence
            rows = self._scan(sequence, b"", None)
        durable_mkdir(target, exist_ok=False)
        digest = hashlib.sha256()
        try:
            with Database.open(target) as backup:
                for offset in range(0, len(rows), 100):
                    # Byte-size aware: 100 maximum-sized values must not exceed batch bound.
                    tx = backup.begin()
                    size = 0
                    for key, value in rows[offset : offset + 100]:
                        if size + len(key) + len(value) + 15 > MAX_BATCH:
                            tx.commit()
                            tx = backup.begin()
                            size = 0
                        tx.put(key, value)
                        size += len(key) + len(value) + 15
                        digest.update(len(key).to_bytes(4) + key + len(value).to_bytes(4) + value)
                    tx.commit()
                backup.compact()
            report: dict[str, object] = {
                "format": 1,
                "source_sequence": sequence,
                "records": len(rows),
                "content_sha256": digest.hexdigest(),
            }
            atomic_metadata(target / "BACKUP", report)
            return report
        except BaseException:
            # Preserve failed outputs for diagnosis; never erase caller-selected paths.
            raise

    @classmethod
    def restore(cls, backup: str | Path, destination: str | Path) -> dict[str, object]:
        expected = read_metadata(Path(backup) / "BACKUP")
        # Validate the envelope before opening the backup: normal open can
        # truncate a torn WAL tail or retire orphan files, so even source-side
        # recovery must not happen for an unsupported backup format/schema.
        required = {"format", "source_sequence", "records", "content_sha256"}
        version = expected.get("format")
        sequence = expected.get("source_sequence")
        records = expected.get("records")
        checksum = expected.get("content_sha256")
        if (
            set(expected) != required
            or type(version) is not int
            or version != 1
            or type(sequence) is not int
            or not 0 <= sequence < 2**64
            or type(records) is not int
            or records < 0
            or not isinstance(checksum, str)
            or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
        ):
            raise Corruption("unsupported or malformed backup metadata")
        with cls.open(backup) as source:
            digest = hashlib.sha256()
            with source.snapshot() as snap:
                rows = list(snap.scan())
            for key, value in rows:
                digest.update(len(key).to_bytes(4) + key + len(value).to_bytes(4) + value)
            if expected.get("content_sha256") != digest.hexdigest() or expected.get(
                "records"
            ) != len(rows):
                raise Corruption("backup content digest mismatch")
            return source.backup(destination)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._check()
                # Attempt every release even if a close reports an I/O error;
                # otherwise a WAL failure can strand tables and the owner lock.
                with ExitStack() as cleanup:
                    cleanup.callback(os.close, self._owner_fd)
                    cleanup.callback(fcntl.flock, self._owner_fd, fcntl.LOCK_UN)
                    for table in self._tables:
                        cleanup.callback(table.close)
                    cleanup.callback(self._wal.close)
                    self._closed = True

    def __enter__(self) -> Self:
        self._check()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class Snapshot:
    def __init__(self, db: Database, sequence: int) -> None:
        self._db = db
        self.sequence = sequence
        self._closed = False
        self._db._pins[sequence] += 1

    def _check(self) -> None:
        if self._closed:
            raise Closed("snapshot closed")
        self._db._check()

    def get(self, key: bytes) -> bytes | None:
        validate(key)
        self._check()
        return self._db._get(key, self.sequence)

    def scan(self, start: bytes = b"", stop: bytes | None = None) -> Iterator[tuple[bytes, bytes]]:
        validate(start)
        if stop is not None:
            validate(stop)
        self._check()
        return iter(self._db._scan(self.sequence, start, stop))

    def close(self) -> None:
        with self._db._lock:
            if not self._closed:
                self._db._pins[self.sequence] -= 1
                if not self._db._pins[self.sequence]:
                    del self._db._pins[self.sequence]
                self._closed = True

    def __enter__(self) -> Self:
        self._check()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class Transaction(Snapshot):
    def __init__(self, db: Database, sequence: int) -> None:
        super().__init__(db, sequence)
        self._writes: dict[bytes, bytes | None] = {}
        self._batch_size = 0

    def put(self, key: bytes, value: bytes) -> None:
        validate(key, value)
        if value is None:
            raise TypeError("put requires a byte value; use delete")
        self._write(key, value)

    def delete(self, key: bytes) -> None:
        validate(key)
        self._write(key, None)

    def _write(self, key: bytes, value: bytes | None) -> None:
        self._check()
        previous = len(key) + len(self._writes[key] or b"") + 15 if key in self._writes else 0
        size = self._batch_size - previous + len(key) + len(value or b"") + 15
        if size > MAX_BATCH:
            raise ValueError("transaction exceeds 16 MiB")
        self._writes[key] = value
        self._batch_size = size

    def get(self, key: bytes) -> bytes | None:
        validate(key)
        self._check()
        return self._writes[key] if key in self._writes else super().get(key)

    def scan(self, start: bytes = b"", stop: bytes | None = None) -> Iterator[tuple[bytes, bytes]]:
        rows = dict(super().scan(start, stop))
        for key, value in self._writes.items():
            if key >= start and (stop is None or key < stop):
                if value is None:
                    rows.pop(key, None)
                else:
                    rows[key] = value
        return iter(sorted(rows.items()))

    def commit(self) -> int:
        self._check()
        try:
            return self._db._commit(self)
        finally:
            self.close()

    def abort(self) -> None:
        self.close()

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._closed:
            return
        if kind is None:
            self.commit()
        else:
            self.abort()
