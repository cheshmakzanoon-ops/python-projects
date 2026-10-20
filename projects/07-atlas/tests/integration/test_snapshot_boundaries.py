import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from pp_atlas import Document, Engine, Principal
from pp_atlas.ingest.tokenizer import tokenize


def test_nfkc_equivalent_japanese_matches_with_original_source_spans(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert("t", Document("j", "Japanese", "ｶﾞ ﾊﾟ カﾞ"))
    result = engine.search(Principal("t", "r"), '"ガ パ ガ"')
    assert result.total == 1
    assert result.hits[0].snippet == "<mark>ｶﾞ</mark> <mark>ﾊﾟ</mark> <mark>カﾞ</mark>"
    assert [(t.start, t.end) for t in tokenize("ｶﾞ ﾊﾟ")] == [(0, 2), (3, 5)]


@pytest.mark.parametrize("operation", ["search", "upsert", "delete", "acl", "groups", "merge"])
@pytest.mark.parametrize("column,value", [("format", 999), ("tokenizer", "future-tokenizer")])
def test_warm_reader_and_writers_refuse_incompatible_catalog(tmp_path, operation, column, value):
    engine = Engine(tmp_path)
    principal = Principal("t", "reader")
    engine.upsert("t", Document("x", "X", "original"))
    engine.search(principal, "original")  # Warm both snapshot and result caches.
    path = next(tmp_path.rglob("catalog.sqlite3"))
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE state SET {column}=?", (value,))
        before = list(connection.iterdump())
    segments_before = set(path.parent.glob("segments/*"))
    actions = {
        "search": lambda: engine.search(principal, "original"),
        "upsert": lambda: engine.upsert("t", Document("y", "Y", "new")),
        "delete": lambda: engine.delete("t", "x"),
        "acl": lambda: engine.set_acl("t", "x", []),
        "groups": lambda: engine.set_groups("t", "reader", ["ops"]),
        "merge": lambda: engine.merge("t"),
    }
    with pytest.raises(ValueError, match="unsupported catalog/tokenizer"):
        actions[operation]()
    with sqlite3.connect(path) as connection:
        assert list(connection.iterdump()) == before
    assert set(path.parent.glob("segments/*")) == segments_before


def test_compatibility_change_while_segment_is_written_cannot_publish(tmp_path, monkeypatch):
    import pp_atlas.engine as implementation

    engine = Engine(tmp_path)
    engine.upsert("t", Document("x", "X", "original"))
    path = next(tmp_path.rglob("catalog.sqlite3"))
    ready, resume = Event(), Event()
    original = implementation.write_segment

    def pause(*args, **kwargs):
        result = original(*args, **kwargs)
        ready.set()
        assert resume.wait(5)
        return result

    monkeypatch.setattr(implementation, "write_segment", pause)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(engine.upsert, "t", Document("y", "Y", "new"))
        assert ready.wait(5)
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE state SET format=999")
        resume.set()
        with pytest.raises(ValueError, match="unsupported catalog/tokenizer"):
            future.result()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT id FROM documents").fetchall() == [("x",)]


def test_cached_queries_skip_visibility_scan_but_recheck_committed_acl(tmp_path, monkeypatch):
    reader, writer = Engine(tmp_path), Engine(tmp_path)
    principal = Principal("t", "reader")
    writer.upsert("t", Document("x", "X", "term", frozenset({"group:ops"})))
    writer.set_groups("t", "reader", ["ops"])
    calls = 0
    original = reader._visible

    def count(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(reader, "_visible", count)
    assert reader.search(principal, "term").total == 1
    assert reader.search(principal, "term").total == 1
    assert calls == 1
    writer.set_groups("t", "reader", [])
    assert reader.search(principal, "term").total == 0
    assert calls == 2


def test_real_wal_snapshot_cannot_mix_catalog_header_documents_and_groups(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from pp_atlas.catalog import Catalog

    reader, writer = Engine(tmp_path), Engine(tmp_path)
    writer.upsert("t", Document("x", "Old", "original", frozenset({"group:ops"})))
    writer.set_groups("t", "reader", ["ops"])
    reader._catalog("t")
    pinned, resume = Event(), Event()
    original = Catalog.connection

    @contextmanager
    def traced(self):
        with original(self) as connection:

            def trace(statement):
                if statement.startswith("SELECT id,revision"):
                    pinned.set()
                    resume.wait(5)

            connection.set_trace_callback(trace)
            yield connection

    monkeypatch.setattr(Catalog, "connection", traced)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(reader.search, Principal("t", "reader"), "original")
        assert pinned.wait(5)
        writer.upsert("t", Document("x", "New", "replacement", frozenset({"user:hidden"})))
        writer.set_groups("t", "reader", [])
        resume.set()
        result = future.result()
    assert result.hits[0].title == "Old"
    assert result.statistics["N"] == 1
    assert reader.search(Principal("t", "reader"), "replacement").total == 0


def test_sigkill_after_commit_before_acknowledgment_is_durable(tmp_path):
    import signal
    import subprocess
    import sys

    reader = Engine(tmp_path)
    principal = Principal("t", "reader")
    reader.upsert("t", Document("x", "Old", "old"))
    reader.search(principal, "old")
    code = """
import os,signal,sys
from contextlib import contextmanager
from pp_atlas import Engine,Document
from pp_atlas.catalog import Catalog
original=Catalog.transaction
@contextmanager
def die_after_commit(self,*,write=False):
    with original(self,write=write) as connection:
        yield connection
    if write:
        os.kill(os.getpid(),signal.SIGKILL)
Catalog.transaction=die_after_commit
Engine(sys.argv[1]).upsert('t',Document('x','New','durable replacement'))
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)])
    assert result.returncode == -signal.SIGKILL
    assert reader.search(principal, "old").total == 0
    assert reader.fetch(principal, "x").text == "durable replacement"
    assert Engine(tmp_path).search(principal, "durable").total == 1


def test_http_warm_incompatible_catalog_is_unavailable_not_a_query_error(tmp_path):
    from fastapi.testclient import TestClient

    from pp_atlas.api import Identity, create_app

    engine = Engine(tmp_path)
    principal = Principal("t", "reader")
    engine.upsert("t", Document("x", "X", "original"))
    client = TestClient(create_app(engine, {"synthetic-reader-token": Identity(principal)}))
    headers = {"Authorization": "Bearer synthetic-reader-token"}
    assert client.get("/search?q=original", headers=headers).status_code == 200
    with sqlite3.connect(next(tmp_path.rglob("catalog.sqlite3"))) as connection:
        connection.execute("UPDATE state SET format=999")
    for url in ("/search?q=original", "/documents/x", "/export", "/ready"):
        response = client.get(url, headers=headers)
        assert response.status_code == 503
        assert response.json() == {
            "detail": "index integrity failure; administrator intervention required"
        }


def test_merge_publication_retains_concurrent_group_revocation(tmp_path, monkeypatch):
    import pp_atlas.engine as implementation

    merger, writer, reader = Engine(tmp_path), Engine(tmp_path), Engine(tmp_path)
    principal = Principal("t", "reader")
    writer.upsert("t", Document("x", "X", "term", frozenset({"group:ops"})))
    writer.set_groups("t", "reader", ["ops"])
    assert reader.search(principal, "term").total == 1
    pinned, resume = Event(), Event()
    original = implementation.write_segment

    def paused(*args, **kwargs):
        result = original(*args, **kwargs)
        pinned.set()
        assert resume.wait(5)
        return result

    monkeypatch.setattr(implementation, "write_segment", paused)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(merger.merge, "t")
        assert pinned.wait(5)
        writer.set_groups("t", "reader", [])
        resume.set()
        assert future.result() == 2
    assert reader.search(principal, "term").total == 0
    assert Engine(tmp_path).search(principal, "term").total == 0


def test_http_stale_merge_is_a_retryable_conflict(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import pp_atlas.engine as implementation
    from pp_atlas.api import Identity, create_app

    merger, writer = Engine(tmp_path), Engine(tmp_path)
    writer.upsert("t", Document("x", "X", "term"))
    client = TestClient(
        create_app(merger, {"synthetic-admin-token": Identity(Principal("t", "admin"), True)}),
        raise_server_exceptions=False,
    )
    pinned, resume = Event(), Event()
    original = implementation.write_segment

    def paused(*args, **kwargs):
        result = original(*args, **kwargs)
        pinned.set()
        assert resume.wait(5)
        return result

    monkeypatch.setattr(implementation, "write_segment", paused)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(
            client.post, "/merge", headers={"Authorization": "Bearer synthetic-admin-token"}
        )
        assert pinned.wait(5)
        assert writer.delete("t", "x")
        resume.set()
        response = future.result()
    assert response.status_code == 409
    assert response.json() == {
        "detail": "generation changed during merge; retry with a new snapshot"
    }
    assert Engine(tmp_path).search(Principal("t", "reader"), "term").total == 0
