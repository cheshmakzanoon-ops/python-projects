import gzip
import hashlib
import json
import sqlite3
import subprocess
import sys

import pytest

from pp_atlas import CorruptSegment, Engine, Principal
from pp_atlas.catalog import Catalog
from pp_atlas.index.segments import sha256
from pp_atlas.ingest.tokenizer import LEGACY_TOKENIZER_VERSION, TOKENIZER_VERSION
from pp_atlas.maintenance import rebuild


def legacy_fixture(root, tenant):
    """Format-1 golden rows, including the known v1 halfwidth posting and tombstone."""
    catalog = Catalog(root, tenant)
    path = catalog.directory / "segments" / "legacy.jsonl.gz"
    path.parent.mkdir(exist_ok=True)
    rows = [
        ["deleted", "d0", "Deleted", "obsolete", 1, {"obsolete": [0]}],
        ["j", "j0", "Old", "obsolete", 1, {"obsolete": [0]}],
        ["j", "j1", "Japanese", "ｶﾞ", 1, {"ガ": [0]}],
        ["secret", "s1", "Private", "classified", 1, {"classified": [0]}],
    ]
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in [{"format": 1, "tokenizer": LEGACY_TOKENIZER_VERSION}, *rows]:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    with catalog.connection() as connection:
        connection.execute(
            "UPDATE state SET tokenizer=?,generation=4,acl_revision=7,segments=?",
            (LEGACY_TOKENIZER_VERSION, json.dumps([[path.name, sha256(path)]])),
        )
        connection.executemany(
            "INSERT INTO documents VALUES (?,?,?,?)",
            [
                ("j", "j1", '["group:ops"]', '{"type":"guide"}'),
                ("secret", "s1", '["user:owner"]', "{}"),
            ],
        )
        connection.execute("INSERT INTO groups VALUES (?,?)", ("reader", '["ops"]'))
    return catalog


def digest_files(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_executable_multi_tenant_rebuild_preserves_current_text_acls_and_groups(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "rebuilt"
    for tenant in ("t", "other"):
        legacy_fixture(source, tenant)
    before = digest_files(source)
    with pytest.raises(ValueError, match="unsupported"):
        Engine(source).search(Principal("t", "reader"), "ガ")
    # Ordinary read-only WAL recognition may create coordination sidecars. It
    # must preserve every existing source byte; maintenance's immutable offline
    # connection additionally preserves the complete inventory present at entry.
    after_recognition = digest_files(source)
    assert all(after_recognition[name] == value for name, value in before.items())
    assert all(
        name.endswith(("catalog.sqlite3-wal", "catalog.sqlite3-shm"))
        for name in after_recognition.keys() - before.keys()
    )
    before = after_recognition
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pp_atlas.maintenance",
            "--source",
            str(source),
            "--destination",
            str(destination),
            "--tenant",
            "t",
            "--tenant",
            "other",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert set(report) == {"t", "other"}
    assert report["t"] == {"documents": 2, "subjects_with_group_records": 1, "source_generation": 4}
    engine = Engine(destination)
    for tenant in ("t", "other"):
        reader = Principal(tenant, "reader")
        assert engine.search(reader, "ガ").hits[0].snippet == "<mark>ｶﾞ</mark>"
        assert engine.fetch(reader, "j").metadata == {"type": "guide"}
        assert engine.search(reader, "obsolete").total == 0
        assert engine.search(reader, "classified").total == 0
        assert engine.fetch(Principal(tenant, "owner"), "secret").text == "classified"
        engine.set_groups(tenant, "reader", [])
        assert engine.search(reader, "ガ").total == 0
        with sqlite3.connect(Catalog(destination, tenant).path) as connection:
            assert connection.execute("SELECT tokenizer FROM state").fetchone() == (
                TOKENIZER_VERSION,
            )
    assert digest_files(source) == before
    with pytest.raises(FileExistsError):
        rebuild(source, destination, ["t"])


def test_rebuild_refuses_nonlegacy_source_and_missing_revision(tmp_path):
    source = tmp_path / "source"
    catalog = legacy_fixture(source, "t")
    with catalog.connection() as connection:
        connection.execute("UPDATE documents SET revision='missing' WHERE id='j'")
    with pytest.raises(CorruptSegment, match="missing active revisions"):
        rebuild(source, tmp_path / "incomplete", ["t"])
    with pytest.raises(ValueError, match="outside"):
        rebuild(source, source / "nested", ["t"])
    with pytest.raises(ValueError, match="exactly once"):
        rebuild(source, tmp_path / "duplicates", ["t", "t"])
    with catalog.connection() as connection:
        connection.execute("UPDATE state SET tokenizer='unknown-future'")
    with pytest.raises(ValueError, match="supported format-1"):
        rebuild(source, tmp_path / "unknown", ["t"])


def test_rebuild_refuses_live_uncheckpointed_wal(tmp_path):
    source = tmp_path / "source"
    catalog = legacy_fixture(source, "t")
    with catalog.connection() as connection:
        connection.execute("UPDATE state SET acl_revision=acl_revision+1")
        with pytest.raises(ValueError, match="uncheckpointed WAL"):
            rebuild(source, tmp_path / "incomplete", ["t"])


def test_known_v2_unicode16_source_rebuilds_under_both_supported_interpreters(tmp_path):
    import unicodedata

    source = tmp_path / "source"
    destination = tmp_path / "rebuilt"
    catalog = legacy_fixture(source, "t")
    path = catalog.directory / "segments" / "unicode16.jsonl.gz"
    version = "nfkc-casefold-alnum-v2-ucd16.0.0"
    # Cyrillic Tje uppercase/lowercase entered the Unicode database in 16.0.
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"format": 1, "tokenizer": version}) + "\n")
        stream.write(json.dumps(["j", "j1", "New character", "\u1c89", 1, {"\u1c8a": [0]}]) + "\n")
    with catalog.connection() as connection:
        connection.execute("DELETE FROM documents WHERE id!='j'")
        connection.execute(
            "UPDATE state SET tokenizer=?,segments=?",
            (version, json.dumps([[path.name, sha256(path)]])),
        )
    if unicodedata.unidata_version != "16.0.0":
        with pytest.raises(ValueError, match="unsupported catalog/tokenizer"):
            Engine(source).fetch(Principal("t", "reader"), "j")
    rebuild(source, destination, ["t"])
    engine = Engine(destination)
    assert engine.fetch(Principal("t", "reader"), "j").text == "\u1c89"
    assert engine.inspect("t")["terms"] == (1 if unicodedata.unidata_version == "16.0.0" else 0)
