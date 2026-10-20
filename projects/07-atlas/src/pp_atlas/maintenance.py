"""Offline tokenizer rebuild into a new index root, preserving ACLs/groups."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from pp_atlas.catalog import read_snapshot, tenant_directory
from pp_atlas.engine import Engine
from pp_atlas.index.segments import CorruptSegment, read_segment
from pp_atlas.ingest.tokenizer import LEGACY_TOKENIZER_VERSION
from pp_atlas.models import Document

SUPPORTED_SOURCE_TOKENIZERS = frozenset(
    {
        LEGACY_TOKENIZER_VERSION,
        "nfkc-casefold-alnum-v2-ucd15.1.0",
        "nfkc-casefold-alnum-v2-ucd16.0.0",
    }
)


def rebuild(source: Path, destination: Path, tenants: Sequence[str]) -> dict[str, dict[str, int]]:
    """Re-tokenize current source text; never reinterpret or relabel old postings.

    All source processes must be stopped. The destination must not exist and must
    remain offline until this function succeeds. A failed attempt leaves an
    incomplete destination for inspection; it never changes the source.
    """
    if not tenants or len(set(tenants)) != len(tenants):
        raise ValueError("supply each configured tenant exactly once")
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if destination.resolve().is_relative_to(source):
        raise ValueError("rebuild destination must be outside the source root")
    # Exclusive directory creation prevents accidental rebuild over valuable state.
    destination.mkdir(parents=True, exist_ok=False)
    return {tenant: _rebuild_tenant(source, destination, tenant) for tenant in tenants}


def _rebuild_tenant(source: Path, destination: Path, tenant: str) -> dict[str, int]:
    directory = tenant_directory(source, tenant)
    catalog = (directory / "catalog.sqlite3").resolve(strict=True)
    wal = catalog.with_name(catalog.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("source has an uncheckpointed WAL; stop processes and checkpoint first")
    # The source is offline and checkpointed. immutable prevents even SQLite's
    # otherwise permissible read-only WAL/shared-memory sidecar creation.
    with closing(
        sqlite3.connect(catalog.as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as connection:
        connection.execute("BEGIN")
        header = connection.execute(
            "SELECT format,tokenizer FROM state WHERE singleton=1"
        ).fetchone()
        if header is None or header[0] != 1 or header[1] not in SUPPORTED_SOURCE_TOKENIZERS:
            raise ValueError("rebuild source must have a supported format-1 tokenizer")
        source_tokenizer = str(header[1])
        snapshot = read_snapshot(connection)
    engine = Engine(destination)
    seen: set[str] = set()
    batch: list[Document] = []
    for name, checksum in snapshot.segments:
        for record in read_segment(
            directory / "segments" / name,
            checksum,
            tokenizer_version=source_tokenizer,
        ):
            active = snapshot.documents.get(record.id)
            if active is None or active.revision != record.revision:
                continue
            if record.id in seen:
                raise CorruptSegment("duplicate active revision in rebuild source")
            seen.add(record.id)
            batch.append(
                Document(record.id, record.title, record.text, active.acl, active.metadata)
            )
            if len(batch) == 1000:
                engine.upsert_many(tenant, batch)
                batch.clear()
    if seen != snapshot.documents.keys():
        raise CorruptSegment("rebuild source is missing active revisions")
    engine.upsert_many(tenant, batch)
    for subject, groups in snapshot.groups.items():
        engine.set_groups(tenant, subject, groups)
    inspection = engine.inspect(tenant)
    if inspection["documents"] != len(seen):
        raise RuntimeError("rebuilt document count mismatch")
    return {
        "documents": len(seen),
        "subjects_with_group_records": len(snapshot.groups),
        "source_generation": snapshot.generation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--tenant", action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild(args.source, args.destination, args.tenant), sort_keys=True))


if __name__ == "__main__":
    main()
