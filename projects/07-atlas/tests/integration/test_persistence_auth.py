from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from pp_atlas import CorruptSegment, Document, Engine, Principal
from pp_atlas.api import Identity, create_app


def signature(result):
    return (
        result.total,
        [(h.id, h.score, h.snippet) for h in result.hits],
        result.facets,
        result.statistics,
    )


def test_at03_at04_revision_delete_merge_restart(tmp_path):
    engine = Engine(tmp_path)
    p = Principal("tenant", "alice")
    old = engine.upsert("tenant", Document("id", "Old", "obsolete secret"))
    new = engine.upsert("tenant", Document("id", "New", "current visible"))
    assert old != new
    assert engine.search(p, "obsolete").total == 0
    assert engine.fetch(p, "id").text == "current visible"
    before = signature(engine.search(p, '"current visible"'))
    engine.merge("tenant")
    assert signature(Engine(tmp_path).search(p, '"current visible"')) == before
    assert engine.delete("tenant", "id")
    assert not engine.delete("tenant", "id")
    engine.merge("tenant")
    assert Engine(tmp_path).search(p, "").total == 0
    with pytest.raises(KeyError):
        engine.fetch(p, "id")


def test_at05_at06_at07_permissions_cache_and_hidden_statistics(tmp_path):
    engine = Engine(tmp_path)
    alice, bob = Principal("a", "alice"), Principal("a", "bob")
    engine.upsert_many(
        "a",
        [
            Document("public", "Public", "term term ordinary", metadata={"type": "runbook"}),
            Document(
                "private",
                "Secret",
                "term term classified",
                frozenset({"group:ops"}),
                {"type": "secret"},
            ),
        ],
    )
    engine.upsert("b", Document("public", "Other tenant", "other other term"))
    baseline = signature(engine.search(alice, "term"))
    engine.upsert(
        "a",
        Document(
            "private",
            "Secret changed",
            "term " * 1000,
            frozenset({"group:ops"}),
            {"type": "hidden"},
        ),
    )
    assert signature(engine.search(alice, "term")) == baseline
    assert len(engine.export(alice)) == 1
    assert engine.search(Principal("b", "alice"), "term").hits[0].title == "Other tenant"
    with pytest.raises(KeyError):
        engine.fetch(alice, "private")
    engine.set_groups("a", "alice", ["ops"])
    assert engine.search(alice, "term").total == 2
    assert engine.search(bob, "term").total == 1
    engine.set_groups("a", "alice", [])
    assert signature(engine.search(alice, "term")) == baseline
    engine.set_acl("a", "public", ["user:bob"])
    assert engine.search(alice, "term").total == 0
    assert len(engine.export(alice)) == 0
    assert engine.search(bob, "term").total == 1
    with pytest.raises(KeyError):
        engine.set_acl("a", "absent", ["*"])


def test_at03_concurrent_generation_publication(tmp_path):
    writer = Engine(tmp_path)
    reader = Engine(tmp_path)
    p = Principal("a", "r")
    writer.upsert("a", Document("0", "0", "stable phrase"))

    def publish():
        for i in range(1, 16):
            writer.upsert("a", Document(str(i), str(i), "stable phrase"))
            if i % 5 == 0:
                writer.merge("a")

    def read():
        counts = []
        for _ in range(40):
            result = reader.search(p, '"stable phrase"', limit=100)
            counts.append(result.total)
            assert result.total == len(result.hits) == result.visible_documents
            assert len({h.score for h in result.hits}) == 1
        return counts

    with ThreadPoolExecutor(2) as pool:
        write = pool.submit(publish)
        read_result = pool.submit(read)
        write.result()
        counts = read_result.result()
    assert counts == sorted(counts)
    assert reader.search(p, "stable").total == 16


def test_at07_corrupt_segment_even_after_cache(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert("a", Document("x", "x", "find me"))
    p = Principal("a", "r")
    assert engine.search(p, "find").total == 1
    path = next(tmp_path.rglob("*.gz"))
    path.write_bytes(b"corrupt")
    with pytest.raises(CorruptSegment):
        engine.search(p, "find")
    with pytest.raises(CorruptSegment):
        engine.fetch(p, "x")


def test_at05_api_authorization_boundary(tmp_path):
    engine = Engine(tmp_path)
    tokens = {
        "admin-synthetic-token": Identity(Principal("a", "admin"), True),
        "reader-synthetic-token": Identity(Principal("a", "alice")),
        "other-synthetic-token": Identity(Principal("b", "bob")),
    }
    client = TestClient(create_app(engine, tokens))
    admin = {"Authorization": "Bearer admin-synthetic-token"}
    reader = {"Authorization": "Bearer reader-synthetic-token"}
    other = {"Authorization": "Bearer other-synthetic-token"}
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/search").status_code == 401
    assert (
        client.post(
            "/documents",
            json={"id": "x", "title": "Secret", "text": "hidden", "acl": ["user:admin"]},
            headers=admin,
        ).status_code
        == 201
    )
    for headers in [reader, other]:
        assert client.get("/documents/x", headers=headers).status_code == 404
        assert client.get("/export", headers=headers).json()["total"] == 0
        assert client.get("/search?q=hidden", headers=headers).json()["total"] == 0
    assert (
        client.post(
            "/documents", json={"id": "y", "title": "", "text": ""}, headers=reader
        ).status_code
        == 403
    )
    assert (
        client.put("/documents/x/acl", json={"subjects": ["*"]}, headers=admin).status_code == 200
    )
    assert client.get("/documents/x", headers=reader).json()["text"] == "hidden"
    assert client.get('/search?q="unclosed', headers=reader).status_code == 400
    assert client.get("/search?limit=200", headers=reader).status_code == 400
    assert client.get("/ready", headers=admin).status_code == 200
    assert client.post("/merge", headers=admin).status_code == 200
    assert client.put("/groups/alice", json={"subjects": ["ops"]}, headers=admin).status_code == 200
    assert client.post("/documents", content=b"x" * 2_100_001, headers=admin).status_code == 413
    assert (
        client.post(
            "/documents", json={"id": "y", "title": "", "text": "", "tenant": "b"}, headers=admin
        ).status_code
        == 422
    )
    assert client.delete("/documents/x", headers=admin).json() == {"deleted": True}
    with pytest.raises(ValueError):
        create_app(engine, {"short": Identity(Principal("a", "b"))})


def test_readiness_does_not_expose_hidden_corpus_statistics(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert("a", Document("public", "Public", "visible"))
    reader = {"Authorization": "Bearer reader-synthetic-token"}
    client = TestClient(
        create_app(engine, {"reader-synthetic-token": Identity(Principal("a", "alice"))})
    )
    assert client.get("/ready").status_code == 401
    before = client.get("/ready", headers=reader)
    assert before.status_code == 200
    engine.upsert(
        "a", Document("private", "Private", "classified vocabulary", frozenset({"user:admin"}))
    )
    after = client.get("/ready", headers=reader)
    assert after.status_code == 200
    assert before.json() == after.json() == {"status": "ready"}
    assert client.get("/search?q=classified", headers=reader).json()["total"] == 0
    next(tmp_path.rglob("*.gz")).write_bytes(b"corrupt")
    assert client.get("/ready", headers=reader).status_code == 503


def test_non_ascii_bearer_credentials_are_rejected_without_server_error(tmp_path):
    client = TestClient(
        create_app(Engine(tmp_path), {"reader-synthetic-token": Identity(Principal("a", "alice"))}),
        raise_server_exceptions=False,
    )
    response = client.get("/search", headers=[(b"authorization", b"Bearer invalid-\xff-token")])
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_atomic_catalog_rollback_and_orphan_ignored(tmp_path):
    import subprocess
    import sys

    engine = Engine(tmp_path)
    engine.upsert("a", Document("x", "Committed", "durable"))
    catalog = next(tmp_path.rglob("catalog.sqlite3"))
    # A separate process dies with an active SQLite publication transaction.
    code = "import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM documents');c.execute('UPDATE state SET generation=generation+1');os._exit(23)"
    assert subprocess.run([sys.executable, "-c", code, str(catalog)]).returncode == 23
    (catalog.parent / "segments" / "orphan.jsonl.gz").write_text("unpublished garbage")
    assert Engine(tmp_path).fetch(Principal("a", "r"), "x").text == "durable"


def test_inflight_request_pins_acl_but_next_request_observes_revoke(tmp_path, monkeypatch):
    from threading import Event

    reader, writer = Engine(tmp_path), Engine(tmp_path)
    writer.upsert("t", Document("x", "x", "permitted", frozenset({"user:alice"})))
    pinned, resume = Event(), Event()
    original = reader._visible

    def paused(principal, snapshot, query):
        pinned.set()
        assert resume.wait(5)
        return original(principal, snapshot, query)

    monkeypatch.setattr(reader, "_visible", paused)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(reader.search, Principal("t", "alice"), "permitted")
        assert pinned.wait(5)
        writer.set_acl("t", "x", ["user:bob"])
        resume.set()
        assert future.result().total == 1
    monkeypatch.setattr(reader, "_visible", original)
    assert reader.search(Principal("t", "alice"), "permitted").total == 0


def test_offline_copy_restore_preserves_authorized_results(tmp_path):
    import shutil

    source = tmp_path / "source"
    restored = tmp_path / "restored"
    engine = Engine(source)
    engine.upsert("t", Document("x", "Restorable", "durable phrase", frozenset({"group:ops"})))
    engine.set_groups("t", "reader", ["ops"])
    principal = Principal("t", "reader")
    before = signature(engine.search(principal, '"durable phrase"'))
    shutil.copytree(source, restored)
    assert signature(Engine(restored).search(principal, '"durable phrase"')) == before
    assert Engine(restored).fetch(principal, "x").title == "Restorable"


def test_two_independent_writers_never_lose_published_segments(tmp_path):
    first, second = Engine(tmp_path), Engine(tmp_path)
    first.inspect("t")
    second.inspect("t")

    def write(engine, prefix):
        for number in range(6):
            engine.upsert("t", Document(f"{prefix}-{number}", prefix, "committed"))

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(write, first, "a")
        b = pool.submit(write, second, "b")
        a.result()
        b.result()
    result = Engine(tmp_path).search(Principal("t", "r"), "committed", limit=100)
    assert result.total == 12
    assert {hit.id for hit in result.hits} == {
        f"{prefix}-{number}" for prefix in ["a", "b"] for number in range(6)
    }


def test_process_dies_after_fsynced_segment_before_catalog_publication(tmp_path):
    import subprocess
    import sys
    import textwrap

    engine = Engine(tmp_path)
    engine.upsert("t", Document("before", "Committed", "existing"))
    code = textwrap.dedent("""
        import os,sys
        from pp_atlas import Document,Engine
        import pp_atlas.engine as module
        original = module.write_segment
        def interrupted(directory, records):
            original(directory, records)
            os._exit(24)
        module.write_segment = interrupted
        Engine(sys.argv[1]).upsert('t', Document('after', 'Unpublished', 'uncommitted'))
    """)
    assert subprocess.run([sys.executable, "-c", code, str(tmp_path)]).returncode == 24
    restarted = Engine(tmp_path)
    assert restarted.search(Principal("t", "r"), "uncommitted").total == 0
    assert restarted.fetch(Principal("t", "r"), "before").text == "existing"
    assert len(list(tmp_path.rglob("*.gz"))) == 2
