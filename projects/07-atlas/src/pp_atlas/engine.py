"""Permission-first lexical engine with immutable reader generations."""

import hashlib
import heapq
import json
import threading
from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from pp_atlas.auth import Principal
from pp_atlas.cache import LRU
from pp_atlas.catalog import Catalog, CatalogSnapshot
from pp_atlas.index.postings import Postings, has_phrase
from pp_atlas.index.segments import CorruptSegment, Record, make_record, read_segment, write_segment
from pp_atlas.ingest.tokenizer import tokenize
from pp_atlas.models import Document, Hit, SearchResult
from pp_atlas.query import Query, parse
from pp_atlas.ranking.bm25 import contribution
from pp_atlas.snippets import snippet


@dataclass
class Generation:
    number: int
    records: dict[str, Record]
    postings: Postings
    signatures: tuple[tuple[str, int, int], ...]


class Engine:
    """Trusted library boundary. Authenticate users before constructing Principal.

    Each request pins a coherent SQLite snapshot. In-progress requests may finish
    under their pinned ACL; requests starting after a revoke commits observe it.
    """

    def __init__(self, root: str | Path, *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("invalid BM25 parameters")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.k1 = k1
        self.b = b
        self._catalogs: dict[str, Catalog] = {}
        self._snapshots: dict[str, CatalogSnapshot] = {}
        self._generations: dict[str, Generation] = {}
        self._cache: LRU[SearchResult] = LRU()
        self._lock = threading.RLock()

    def _catalog(self, tenant: str) -> Catalog:
        if tenant not in self._catalogs:
            self._catalogs[tenant] = Catalog(self.root, tenant)
        return self._catalogs[tenant]

    def upsert(self, tenant: str, document: Document) -> str:
        return self.upsert_many(tenant, [document])[document.id]

    def upsert_many(self, tenant: str, documents: Iterable[Document]) -> dict[str, str]:
        """Atomic batch, bounded to 100k docs; crash-before-publication leaves an orphan.

        No search can observe the segment until all revisions publish in one txn.
        Concurrent writers append to the generation current at transaction time.
        """
        with self._lock:
            catalog = self._catalog(tenant)
            docs: dict[str, Document] = {}
            records: dict[str, Record] = {}
            for document in documents:
                if document.id in docs:
                    raise ValueError("duplicate document id in batch")
                docs[document.id] = document
                records[document.id] = make_record(document)
                if len(docs) > 100_000:
                    raise ValueError("batch exceeds 100000 documents")
            if not docs:
                return {}
            segment = write_segment(
                catalog.directory / "segments", (records[ident] for ident in sorted(records))
            )
            with catalog.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                segments = json.loads(
                    connection.execute("SELECT segments FROM state").fetchone()[0]
                )
                segments.append(segment)
                connection.executemany(
                    "INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,acl=excluded.acl,metadata=excluded.metadata",
                    [
                        (
                            ident,
                            records[ident].revision,
                            json.dumps(sorted(doc.acl)),
                            json.dumps(doc.metadata),
                        )
                        for ident, doc in docs.items()
                    ],
                )
                connection.execute(
                    "UPDATE state SET generation=generation+1,acl_revision=acl_revision+1,segments=?",
                    (json.dumps(segments),),
                )
                connection.commit()
            return {ident: record.revision for ident, record in records.items()}

    def delete(self, tenant: str, document_id: str) -> bool:
        with self._lock:
            catalog = self._catalog(tenant)
            with catalog.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                deleted = (
                    connection.execute("DELETE FROM documents WHERE id=?", (document_id,)).rowcount
                    > 0
                )
                if deleted:
                    connection.execute(
                        "UPDATE state SET generation=generation+1,acl_revision=acl_revision+1"
                    )
                connection.commit()
                return deleted

    def set_acl(self, tenant: str, document_id: str, acl: Iterable[str]) -> None:
        subjects = frozenset(acl)
        Document(document_id, "", "", subjects)  # Validate ACL bounds before persistence.
        with self._lock:
            with self._catalog(tenant).connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if (
                    connection.execute(
                        "UPDATE documents SET acl=? WHERE id=?",
                        (json.dumps(sorted(subjects)), document_id),
                    ).rowcount
                    != 1
                ):
                    raise KeyError(document_id)
                connection.execute("UPDATE state SET acl_revision=acl_revision+1")
                connection.commit()

    def set_groups(self, tenant: str, subject: str, groups: Iterable[str]) -> None:
        Principal(tenant, subject)
        memberships = frozenset(groups)
        if any(not g or len(g) > 256 for g in memberships) or len(memberships) > 128:
            raise ValueError("invalid groups")
        with self._lock:
            with self._catalog(tenant).connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO groups VALUES (?,?) ON CONFLICT(subject) DO UPDATE SET memberships=excluded.memberships",
                    (subject, json.dumps(sorted(memberships))),
                )
                connection.execute("UPDATE state SET acl_revision=acl_revision+1")
                connection.commit()

    def _snapshot(self, tenant: str) -> tuple[CatalogSnapshot, Generation]:
        catalog = self._catalog(tenant)
        snapshot = catalog.snapshot(self._snapshots.get(tenant))
        signatures: list[tuple[str, int, int]] = []
        try:
            for name, _ in snapshot.segments:
                stat = (catalog.directory / "segments" / name).stat()
                signatures.append((name, stat.st_size, stat.st_mtime_ns))
        except OSError as error:
            raise CorruptSegment("referenced segment missing") from error
        generation = self._generations.get(tenant)
        if (
            generation is None
            or generation.number != snapshot.generation
            or generation.signatures != tuple(signatures)
        ):
            records: dict[str, Record] = {}
            for name, checksum in snapshot.segments:
                for record in read_segment(catalog.directory / "segments" / name, checksum):
                    active = snapshot.documents.get(record.id)
                    if active and active.revision == record.revision:
                        if record.id in records:
                            raise CorruptSegment("duplicate active revision in segments")
                        records[record.id] = record
            if records.keys() != snapshot.documents.keys():
                raise CorruptSegment("catalog revision absent from published segments")
            postings: Postings = defaultdict(dict)
            for ident, record in records.items():
                for term, offsets in record.positions.items():
                    postings[term][ident] = offsets
            generation = Generation(snapshot.generation, records, dict(postings), tuple(signatures))
            self._generations[tenant] = generation
        self._snapshots[tenant] = snapshot
        return snapshot, generation

    @staticmethod
    def _visible(principal: Principal, snapshot: CatalogSnapshot, query: Query) -> set[str]:
        permissions = {"*", f"user:{principal.subject}"}
        permissions.update(f"group:{g}" for g in snapshot.groups.get(principal.subject, ()))
        return {
            ident
            for ident, active in snapshot.documents.items()
            if active.acl.intersection(permissions)
            and all(
                (ident if key == "id" else active.metadata.get(key)) == value
                for key, value in query.filters
            )
        }

    def search(
        self, principal: Principal, query: str, *, limit: int = 10, offset: int = 0
    ) -> SearchResult:
        if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
            raise ValueError("invalid limit/offset")
        parsed = parse(query)
        with self._lock:
            snapshot, generation = self._snapshot(principal.tenant)
            visible = self._visible(principal, snapshot, parsed)
            digest = hashlib.sha256(
                json.dumps(sorted(visible), separators=(",", ":")).encode()
            ).hexdigest()
            key = (
                principal.tenant,
                principal.subject,
                digest,
                snapshot.acl_revision,
                snapshot.generation,
                parsed.key,
                self.k1,
                self.b,
                limit,
                offset,
            )
            cached = self._cache.get(key)
            if cached is not None:
                return deepcopy(cached)
            candidates = visible.copy()
            for term in parsed.terms:
                candidates.intersection_update(generation.postings.get(term, {}))
            for phrase in parsed.phrases:
                candidates = {
                    ident
                    for ident in candidates
                    if has_phrase(generation.records[ident].positions, phrase)
                }
            average = (
                sum(generation.records[ident].length for ident in visible) / len(visible)
                if visible
                else 0.0
            )
            dfs = {
                term: len(visible.intersection(generation.postings.get(term, {})))
                for term in parsed.terms
            }

            def explain(ident: str) -> dict[str, float]:
                record = generation.records[ident]
                return {
                    term: contribution(
                        len(record.positions[term]),
                        record.length,
                        len(visible),
                        dfs[term],
                        average,
                        k1=self.k1,
                        b=self.b,
                    )
                    for term in parsed.terms
                }

            ranked = heapq.nsmallest(
                offset + limit, ((-sum(explain(ident).values()), ident) for ident in candidates)
            )
            hits = tuple(
                Hit(
                    ident,
                    generation.records[ident].revision,
                    generation.records[ident].title,
                    -negative,
                    snippet(
                        generation.records[ident].text,
                        tokenize(generation.records[ident].text),
                        frozenset(parsed.terms),
                    ),
                    explain(ident),
                )
                for negative, ident in ranked[offset:]
            )
            facets = dict(
                Counter(
                    snapshot.documents[ident].metadata.get("type", "unknown")
                    for ident in candidates
                )
            )
            result = SearchResult(
                snapshot.generation,
                snapshot.acl_revision,
                len(candidates),
                hits,
                facets,
                len(visible),
                {
                    "N": len(visible),
                    "average_length": average,
                    "document_frequency": dfs,
                    "k1": self.k1,
                    "b": self.b,
                },
            )
            self._cache.put(key, deepcopy(result))
            return result

    def fetch(self, principal: Principal, document_id: str) -> Document:
        with self._lock:
            snapshot, generation = self._snapshot(principal.tenant)
            if document_id not in self._visible(
                principal, snapshot, Query((), (), (("id", document_id),))
            ):
                raise KeyError(document_id)  # Same response for absent and forbidden IDs.
            record = generation.records[document_id]
            active = snapshot.documents[document_id]
            return Document(record.id, record.title, record.text, active.acl, dict(active.metadata))

    def authorized_ids(self, principal: Principal) -> tuple[str, ...]:
        """A pinned authorized identity snapshot, also useful for cost measurement."""
        with self._lock:
            snapshot, _ = self._snapshot(principal.tenant)
            return tuple(sorted(self._visible(principal, snapshot, Query((), (), ()))))

    def export(self, principal: Principal) -> tuple[Document, ...]:
        with self._lock:
            snapshot, generation = self._snapshot(principal.tenant)
            visible = self._visible(principal, snapshot, Query((), (), ()))
            return tuple(
                Document(
                    ident,
                    generation.records[ident].title,
                    generation.records[ident].text,
                    snapshot.documents[ident].acl,
                    dict(snapshot.documents[ident].metadata),
                )
                for ident in sorted(visible)
            )

    def merge(self, tenant: str) -> int:
        """Streaming segment output; transaction checks prevent lost concurrent writes.

        Old segments remain for pinned readers. Offline garbage collection requires
        exclusive maintenance and is deliberately separate from publication.
        """
        with self._lock:
            catalog = self._catalog(tenant)
            snapshot = catalog.snapshot()
            streams = [
                read_segment(catalog.directory / "segments" / name, checksum)
                for name, checksum in snapshot.segments
            ]
            seen: set[str] = set()

            def active_records() -> Iterable[Record]:
                for record in heapq.merge(*streams, key=lambda record: record.id):
                    active = snapshot.documents.get(record.id)
                    if active and active.revision == record.revision:
                        if record.id in seen:
                            raise CorruptSegment("duplicate active revision in segments")
                        seen.add(record.id)
                        yield record

            segment = write_segment(catalog.directory / "segments", active_records())
            if seen != snapshot.documents.keys():
                raise CorruptSegment("merge found missing current revisions")
            with catalog.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute("SELECT generation FROM state").fetchone()[0]
                if current != snapshot.generation:
                    raise RuntimeError("generation changed during merge; retry with a new snapshot")
                connection.execute(
                    "UPDATE state SET generation=generation+1,segments=?", (json.dumps([segment]),)
                )
                connection.commit()
                return int(current) + 1

    def inspect(self, tenant: str) -> dict[str, object]:
        with self._lock:
            snapshot, generation = self._snapshot(tenant)
            return {
                "generation": snapshot.generation,
                "acl_revision": snapshot.acl_revision,
                "documents": len(generation.records),
                "segments": len(snapshot.segments),
                "terms": len(generation.postings),
            }
