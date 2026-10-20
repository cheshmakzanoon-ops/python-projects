"""Bounded staged ingest and partition-local three-node transactional publication."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from pp_quarry.contracts import Contract
from pp_quarry.model.events import canonical
from pp_quarry.planning.dag import DEFAULT_DAG, Node, fingerprint, order
from pp_quarry.planning.partitions import bucket
from pp_quarry.sources import file_hash, read
from pp_quarry.storage.catalog import check_storage_paths, connect, read_format
from pp_quarry.storage.files import literal, manifest_path, persist, verify_entry
from pp_quarry.storage.manifest import validate_manifest


class Conflict(ValueError):
    """An already accepted key/version has different content."""


class InjectedCrash(RuntimeError):
    """Deterministic fault boundary; CLI can replace with process termination."""


@dataclass(frozen=True)
class Config:
    buckets: int = 8
    batch_size: int = 1024
    memory_mb: int = 128
    threads: int = 1
    max_record_bytes: int = 65536

    def __post_init__(self) -> None:
        if any(
            type(value) is not int
            for value in (
                self.buckets,
                self.batch_size,
                self.memory_mb,
                self.threads,
                self.max_record_bytes,
            )
        ):
            raise ValueError("resource settings must be integers, not booleans or fractions")
        bucket(b"validate", self.buckets)
        if self.batch_size < 1 or self.memory_mb < 32 or self.threads not in {1, 2}:
            raise ValueError("batch >=1, memory >=32 MB and threads 1..2 required")
        if (
            self.max_record_bytes < 128
            or self.batch_size * self.max_record_bytes > self.memory_mb * 1024 * 1024 // 2
        ):
            raise ValueError("configured batch/record bound exceeds half of memory budget")


def code_digest() -> str:
    digest = hashlib.sha256()
    digest.update(canonical([pa.__version__, duckdb.__version__]).encode())
    for path in sorted(Path(__file__).parents[1].rglob("*.py")):
        digest.update(path.relative_to(Path(__file__).parents[1]).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class Lakehouse:
    def __init__(self, root: str | Path, config: Config | None = None) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root / ".quarry-owned"
        if not marker.exists() and any(self.root.iterdir()):
            raise ValueError("dataset root must be empty or owned by Quarry")
        check_storage_paths(self.root)
        marker.touch(exist_ok=True)
        (self.root / "data").mkdir(exist_ok=True)
        (self.root / "tmp").mkdir(exist_ok=True)
        self.db = connect(self.root)
        try:
            self._configure(config)
        except BaseException:
            self.db.close()
            raise

    def _configure(self, config: Config | None) -> None:
        stored = read_format(self.db)
        self.config = config or (Config(**stored["config"]) if stored else Config())
        if stored and stored["config"]["buckets"] != self.config.buckets:
            raise ValueError("bucket count migration required")
        if not stored:
            from dataclasses import asdict

            self.db.execute(
                "INSERT INTO config VALUES (?,?)",
                (
                    "format",
                    canonical(
                        {
                            "format_version": 1,
                            "bucket_hash": "sha256-canonical-key-first8-big-endian",
                            "salt": None,
                            "config": asdict(self.config),
                        }
                    ),
                ),
            )
            self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Lakehouse:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def manifest(self, snapshot: int | None = None) -> dict[str, Any]:
        row = (
            self.db.execute("SELECT id,manifest FROM snapshots WHERE id=?", (snapshot,)).fetchone()
            if snapshot is not None
            else self.db.execute(
                "SELECT id,manifest FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        )
        if row is None:
            if snapshot is not None:
                raise ValueError(f"unknown snapshot {snapshot}")
            return {"snapshot": None, "partitions": {}, "contract": Contract().to_dict()}
        return dict(validate_manifest(json.loads(row[1]), self.config.buckets), snapshot=row[0])

    def snapshots(self) -> list[int]:
        return [row[0] for row in self.db.execute("SELECT id FROM snapshots ORDER BY id")]

    def _contract(self) -> Contract:
        row = self.db.execute("SELECT value FROM config WHERE key='contract'").fetchone()
        return Contract.from_dict(json.loads(row[0])) if row else Contract()

    def _partition_input(self, partition: int) -> str:
        digest = hashlib.sha256()
        for row in self.db.execute(
            "SELECT namespace,key,fingerprint FROM latest WHERE bucket=? ORDER BY namespace,key",
            (partition,),
        ):
            digest.update(canonical(row).encode())
        return digest.hexdigest()

    @staticmethod
    def _graph(dag: tuple[Node, ...]) -> tuple[Node, ...]:
        resolved = order(dag)
        expected = {node.name: (node.transform, node.parents) for node in DEFAULT_DAG}
        actual = {node.name: (node.transform, node.parents) for node in resolved}
        if actual != expected:
            raise ValueError(
                "unsupported pipeline configuration: require normalized -> facts -> daily with their declared transforms"
            )
        return resolved

    def _plan(self, contract: Contract, dag: tuple[Node, ...]) -> dict[str, Any]:
        previous = self.manifest()
        semantic = code_digest()
        entries: dict[str, Any] = {}
        for partition in range(self.config.buckets):
            upstream = self._partition_input(partition)
            nodes: dict[str, Any] = {}
            for node in self._graph(dag):
                inputs = [nodes[parent]["fingerprint"] for parent in node.parents] or [upstream]
                digest = fingerprint(
                    node,
                    inputs,
                    canonical(
                        {
                            "contract": contract.to_dict(),
                            "compression": "zstd",
                            "duckdb_threads": self.config.threads,
                            "format_version": 1,
                        }
                    ),
                    semantic,
                )
                old = previous["partitions"].get(str(partition), {}).get(node.name)
                nodes[node.name] = {
                    "fingerprint": digest,
                    "action": "reuse" if old and old["fingerprint"] == digest else "build",
                    "old": old,
                }
            entries[str(partition)] = nodes
        return {
            "partitions": entries,
            "contract": contract.to_dict(),
            "base_snapshot": previous["snapshot"],
            "code_digest": semantic,
        }

    def plan(
        self,
        source: str | Path | None = None,
        contract: Contract | None = None,
        dag: tuple[Node, ...] = DEFAULT_DAG,
    ) -> dict[str, Any]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            chosen = self._prepare_contract(contract)
            if source is not None:
                self._stage(Path(source), chosen)
            return self._plan(chosen, dag)
        finally:
            self.db.rollback()

    def _prepare_contract(self, contract: Contract | None) -> Contract:
        chosen = contract or self._contract()
        if self.db.execute("SELECT 1 FROM config WHERE key='contract'").fetchone():
            chosen.compatible(self._contract())
        return chosen

    def _stage(self, source: Path, contract: Contract) -> tuple[str, int, int]:
        digest = file_hash(source)
        prior = self.db.execute(
            "SELECT offset,events FROM sources WHERE hash=?", (digest,)
        ).fetchone()
        if prior:
            return digest, prior[0], prior[1]
        offset = count = 0
        consumed = hashlib.sha256()
        for offset, event in read(source, self.config.max_record_bytes, observe=consumed.update):
            contract.validate(event)
            count += 1
            if event.version > 2**63 - 1:
                raise ValueError("version exceeds SQLite signed 64-bit format")
            accepted = self.db.execute(
                "SELECT fingerprint FROM identities WHERE namespace=? AND key=? AND version=?",
                (event.namespace, event.key, event.version),
            ).fetchone()
            if accepted:
                if accepted[0] != event.fingerprint:
                    raise Conflict(
                        f"historical equal-version conflict: {event.namespace}/{event.key}@{event.version}"
                    )
                continue
            payload = canonical(event.payload)
            self.db.execute(
                "INSERT INTO identities VALUES (?,?,?,?,?,?,?,?)",
                (
                    event.namespace,
                    event.key,
                    event.version,
                    event.fingerprint,
                    payload,
                    event.operation,
                    digest,
                    offset,
                ),
            )
            self.db.execute(
                "INSERT INTO latest VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET version=excluded.version,operation=excluded.operation,payload=excluded.payload,fingerprint=excluded.fingerprint,bucket=excluded.bucket,source=excluded.source,offset=excluded.offset WHERE excluded.version>latest.version",
                (
                    event.namespace,
                    event.key,
                    event.version,
                    event.operation,
                    payload,
                    event.fingerprint,
                    bucket(event.key_bytes, self.config.buckets),
                    digest,
                    offset,
                ),
            )
        if consumed.hexdigest() != digest or file_hash(source) != digest:
            raise ValueError("source changed while reading")
        return digest, offset, count

    def ingest(
        self,
        source: str | Path,
        contract: Contract | None = None,
        *,
        fault: str | None = None,
        dag: tuple[Node, ...] = DEFAULT_DAG,
        force_rebuild: bool = False,
    ) -> int:
        self._graph(dag)
        if fault not in {None, "after_files", "before_commit", "after_commit"}:
            raise ValueError("unknown fault boundary")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            chosen = self._prepare_contract(contract)
            digest, offset, count = self._stage(Path(source), chosen)
            plan = self._plan(chosen, dag)
            if force_rebuild:
                for nodes in plan["partitions"].values():
                    for entry in nodes.values():
                        entry["action"] = "build"
            quality = self._quality(chosen, plan)
            manifest = self._execute(plan, dag)
            manifest["quality"] = quality
            validate_manifest(manifest, self.config.buckets)
            if fault == "after_files":
                self._crash(fault)
            if file_hash(Path(source)) != digest:
                raise ValueError("source changed before publication")
            row = self.db.execute(
                "INSERT INTO snapshots(manifest) VALUES (?)", (canonical(manifest),)
            )
            assert row.lastrowid is not None
            snapshot = row.lastrowid
            self.db.execute(
                "INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)",
                (digest, str(Path(source).resolve()), offset, count, snapshot),
            )
            self.db.execute(
                "INSERT OR REPLACE INTO config VALUES ('contract',?)",
                (canonical(chosen.to_dict()),),
            )
            if fault == "before_commit":
                self._crash(fault)
            self.db.commit()
            if fault == "after_commit":
                self._crash(fault)
            return snapshot
        except BaseException:
            self.db.rollback()
            raise

    @staticmethod
    def _crash(boundary: str) -> None:
        if os.environ.get("QUARRY_HARD_CRASH") == "1":
            os._exit(91)
        raise InjectedCrash(boundary)

    def _quality(self, contract: Contract, plan: dict[str, Any]) -> dict[str, Any]:
        previous = self.manifest().get("quality", {}).get("partitions", {})
        partitions: dict[str, Any] = {}
        for partition, nodes in plan["partitions"].items():
            if partition in previous and all(node["action"] == "reuse" for node in nodes.values()):
                partitions[partition] = previous[partition]
            else:
                count, low, high = self.db.execute(
                    "SELECT count(*), min(CASE WHEN json_type(payload,'$.value') IN ('integer','real') THEN json_extract(payload,'$.value') END),max(CASE WHEN json_type(payload,'$.value') IN ('integer','real') THEN json_extract(payload,'$.value') END) FROM latest WHERE operation='upsert' AND bucket=?",
                    (int(partition),),
                ).fetchone()
                partitions[partition] = {"count": count, "minimum": low, "maximum": high}
        count = sum(p["count"] for p in partitions.values())
        minima = [p["minimum"] for p in partitions.values() if p["minimum"] is not None]
        maxima = [p["maximum"] for p in partitions.values() if p["maximum"] is not None]
        low, high = min(minima, default=None), max(maxima, default=None)
        if count < contract.min_rows or (
            contract.max_rows is not None and count > contract.max_rows
        ):
            raise ValueError(
                f"dataset row-count rule: {count} outside [{contract.min_rows}, {contract.max_rows}]"
            )
        if contract.minimum is not None and low is not None and low < contract.minimum:
            raise ValueError(f"dataset minimum rule: {low} below {contract.minimum}")
        if contract.maximum is not None and high is not None and high > contract.maximum:
            raise ValueError(f"dataset maximum rule: {high} above {contract.maximum}")
        return {
            "scope": "global reduction of partition-local summaries",
            "partitions": partitions,
            "live_rows": count,
            "minimum_value": low,
            "maximum_value": high,
        }

    def build(self, *, force: bool = False) -> int:
        source = self.root / "tmp" / f"empty-{uuid.uuid4().hex}.ndjson"
        source.touch()
        try:
            return self.ingest(source, force_rebuild=force)
        finally:
            source.unlink()

    def _batches(self, partition: int) -> Iterator[list[tuple[Any, ...]]]:
        cursor = self.db.execute(
            "SELECT namespace,key,version,operation,payload,source,offset FROM latest WHERE bucket=? ORDER BY namespace,key",
            (partition,),
        )
        while rows := cursor.fetchmany(self.config.batch_size):
            yield rows

    def _execute(self, plan: dict[str, Any], dag: tuple[Node, ...]) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "format_version": 1,
            "execution_settings": {
                "memory_mb": self.config.memory_mb,
                "threads": self.config.threads,
            },
            "contract": plan["contract"],
            "partitions": {},
            "base_snapshot": plan["base_snapshot"],
            "code_digest": plan["code_digest"],
            "stats": {
                "rewritten_buckets": 0,
                "reused_nodes": 0,
                "bytes_written": 0,
                "parquet_input_bytes": 0,
                "max_batch_rows": 0,
            },
            "column_lineage": {
                "facts.device": "normalized.payload.device",
                "facts.day": "normalized.payload.day",
                "facts.value": "normalized.payload.value",
                "daily.total": "sum(facts.value)",
                "daily.count": "count(facts.key)",
            },
        }
        schema = pa.schema(
            [
                ("namespace", pa.string()),
                ("key", pa.string()),
                ("version", pa.int64()),
                ("operation", pa.string()),
                ("payload", pa.string()),
                ("source", pa.string()),
                ("offset", pa.int64()),
            ]
        )
        with duckdb.connect() as engine:
            engine.execute(f"SET memory_limit='{self.config.memory_mb}MB'")
            engine.execute(f"SET threads={self.config.threads}")
            engine.execute(f"SET temp_directory={literal(str(self.root / 'tmp'))}")
            for part, nodes in plan["partitions"].items():
                output: dict[str, Any] = {}
                rewritten = False
                for node in self._graph(dag):
                    entry = nodes[node.name]
                    if entry["action"] == "reuse":
                        verify_entry(self.root, entry["old"])
                        output[node.name] = dict(entry["old"], reused=True)
                        manifest["stats"]["reused_nodes"] += 1
                        continue
                    rewritten = True
                    path = self.root / "data" / f"{node.name}-{part}-{uuid.uuid4().hex}.parquet"
                    if node.transform == "normalize":
                        with pq.ParquetWriter(path, schema, compression="zstd") as writer:
                            for rows in self._batches(int(part)):
                                arrays = [
                                    pa.array([r[i] for r in rows], type=field.type)
                                    for i, field in enumerate(schema)
                                ]
                                writer.write_batch(pa.record_batch(arrays, schema=schema))
                                manifest["stats"]["max_batch_rows"] = max(
                                    manifest["stats"]["max_batch_rows"], len(rows)
                                )
                    else:
                        parent = manifest_path(self.root, output[node.parents[0]]["path"])
                        manifest["stats"]["parquet_input_bytes"] += parent.stat().st_size
                        if node.transform == "facts":
                            extras = []
                            contract = Contract.from_dict(plan["contract"])
                            kinds = {
                                "string": "VARCHAR",
                                "number": "DOUBLE",
                                "integer": "BIGINT",
                                "boolean": "BOOLEAN",
                                "json": "JSON",
                            }
                            for name, field in contract.fields.items():
                                if name in {"device", "day", "value"}:
                                    continue
                                pointer = "/" + name.replace("~", "~0").replace("/", "~1")
                                alias = '"payload__' + name.replace('"', '""') + '"'
                                extract = (
                                    "json_extract"
                                    if field.kind == "json"
                                    else "json_extract_string"
                                )
                                expression = f"{extract}(payload,{literal(pointer)})"
                                if field.kind == "json":
                                    # JSON null represents an absent nullable value; the
                                    # JSON string "null" remains a distinct JSON scalar.
                                    expression = f"nullif({expression},'null'::JSON)"
                                extras.append(
                                    f"try_cast({expression} AS {kinds[field.kind]}) AS {alias}"
                                )
                            projection = "," + ",".join(extras) if extras else ""
                            sql = f"SELECT namespace,key,version,json_extract_string(payload,'$.device') device,json_extract_string(payload,'$.day') AS \"day\",coalesce(try_cast(json_extract_string(payload,'$.value') AS DOUBLE),0) AS \"value\",payload,source,\"offset\"{projection} FROM read_parquet({literal(str(parent))}) WHERE operation='upsert'"
                        else:
                            sql = f'SELECT "day",count(*) count,sum("value") total FROM read_parquet({literal(str(parent))}) GROUP BY "day" ORDER BY "day"'
                        engine.execute(
                            f"COPY ({sql}) TO {literal(str(path))} (FORMAT PARQUET, COMPRESSION ZSTD)"
                        )
                    checksum, size = persist(path)
                    rows_count = pq.ParquetFile(path).metadata.num_rows
                    output[node.name] = {
                        "path": path.relative_to(self.root).as_posix(),
                        "sha256": checksum,
                        "bytes": size,
                        "rows": rows_count,
                        "fingerprint": entry["fingerprint"],
                        "reused": False,
                        "schema": str(pq.read_schema(path)),
                        "transform": node.transform,
                        "parents": list(node.parents),
                        "input_fingerprints": [
                            output[parent]["fingerprint"] for parent in node.parents
                        ]
                        or [self._partition_input(int(part))],
                    }
                    manifest["stats"]["bytes_written"] += size
                manifest["partitions"][part] = output
                manifest["stats"]["rewritten_buckets"] += int(rewritten)
        return manifest

    def lineage(self, namespace: str, key: str) -> dict[str, Any]:
        versions = [
            {
                "version": row[0],
                "fingerprint": row[1],
                "source_sha256": row[2],
                "offset": row[3],
                "operation": row[4],
            }
            for row in self.db.execute(
                "SELECT version,fingerprint,source,offset,operation FROM identities WHERE namespace=? AND key=? ORDER BY version",
                (namespace, key),
            )
        ]
        return {
            "namespace": namespace,
            "key": key,
            "versions": versions,
            "columns": self.manifest().get("column_lineage", {}),
        }

    def validate(self, snapshot: int | None = None) -> dict[str, int]:
        manifest = self.manifest(snapshot)
        files = rows = 0
        for nodes in manifest["partitions"].values():
            for entry in nodes.values():
                verify_entry(self.root, entry)
                files += 1
                rows += entry["rows"]
        return {"files": files, "rows": rows}
