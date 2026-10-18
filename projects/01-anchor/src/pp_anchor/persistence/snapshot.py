"""Versioned PostgreSQL COPY snapshots; verified before a single restore transaction."""

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from psycopg import sql

from pp_anchor.persistence.engine import Engine

TABLES = (
    "workflow_runs",
    "history_events",
    "ingress_requests",
    "activity_tasks",
    "activity_attempts",
    "timers",
    "signals",
    "provider_effects",
)
MAX_BYTES = 100 * 1024 * 1024


def _safe_path(path: Path) -> None:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Snapshot path must be absolute and contain no symlinks")


def backup(engine: Engine, path: Path) -> None:
    _safe_path(path)
    contents: dict[str, bytes] = {}
    total = 0
    with engine.transaction() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table in TABLES:
            buffer = io.BytesIO()
            with c.cursor().copy(
                sql.SQL("COPY {} TO STDOUT").format(sql.Identifier(table))
            ) as copy:
                for chunk in copy:
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError(
                            "Snapshot exceeds 100 MiB bound; use pg_dump for larger databases"
                        )
                    buffer.write(chunk)
            contents[f"{table}.copy"] = buffer.getvalue()
    manifest = {
        "schema_version": 1,
        "tables": {name: hashlib.sha256(value).hexdigest() for name, value in contents.items()},
    }
    with (
        os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as target,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive,
    ):
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, value in contents.items():
            archive.writestr(name, value)


def restore(engine: Engine, path: Path) -> None:
    _safe_path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Snapshot archive exceeds size bound")
    expected = {"manifest.json", *(f"{table}.copy" for table in TABLES)}
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("Unknown, duplicate or missing snapshot members")
        if sum(info.file_size for info in archive.infolist()) > MAX_BYTES:
            raise ValueError("Uncompressed snapshot exceeds size bound")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported snapshot schema version")
        contents = {f"{table}.copy": archive.read(f"{table}.copy") for table in TABLES}
    if manifest.get("tables") != {
        name: hashlib.sha256(value).hexdigest() for name, value in contents.items()
    }:
        raise ValueError("Snapshot checksum mismatch")
    with engine.transaction() as c:
        # Prevent admissions while the complete snapshot is restored.
        c.execute("LOCK TABLE workflow_runs IN ACCESS EXCLUSIVE MODE")
        for table in TABLES:
            if c.execute(
                sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table))
            ).fetchone():
                raise ValueError("Restore target must be empty")
        for table in TABLES:
            with c.cursor().copy(
                sql.SQL("COPY {} FROM STDIN").format(sql.Identifier(table))
            ) as copy:
                copy.write(contents[f"{table}.copy"])
