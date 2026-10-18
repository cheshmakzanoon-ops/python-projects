import gzip
import json

import pytest

from pp_atlas import CorruptSegment, Document, Engine, Principal
from pp_atlas.cache import LRU
from pp_atlas.catalog import Catalog
from pp_atlas.index.segments import read_segment, sha256
from pp_atlas.ingest.tokenizer import TOKENIZER_VERSION


@pytest.mark.parametrize(
    "row",
    [
        None,
        [1, "r", "t", "text", 1, {}],
        ["id", "r", "t", "text", -1, {}],
        ["id", "r", "t", "text", 1, {"term": "bad"}],
        ["id", "r", "t", "text", 1, {"term": [2]}],
        ["id", "r", "t", "text", 2, {"term": [1, 0]}],
    ],
)
def test_valid_checksum_does_not_bypass_format_validation(tmp_path, row):
    path = tmp_path / "bad.gz"
    with gzip.open(path, "wt") as stream:
        stream.write(json.dumps({"format": 1, "tokenizer": TOKENIZER_VERSION}) + "\n")
        stream.write(json.dumps(row) + "\n")
    with pytest.raises(CorruptSegment):
        list(read_segment(path, sha256(path)))


def test_format_version_missing_files_and_catalog_revisions(tmp_path):
    path = tmp_path / "bad.gz"
    with gzip.open(path, "wt") as stream:
        stream.write('{"format":999}\n')
    with pytest.raises(CorruptSegment):
        list(read_segment(path, sha256(path)))
    engine = Engine(tmp_path / "index")
    engine.upsert("t", Document("x", "x", "valid"))
    catalog = Catalog(tmp_path / "index", "t")
    with catalog.connection() as connection:
        connection.execute("UPDATE documents SET revision='nonexistent'")
    with pytest.raises(CorruptSegment):
        engine.search(Principal("t", "r"), "valid")
    with pytest.raises(CorruptSegment):
        engine.merge("t")
    next((tmp_path / "index").rglob("*.gz")).unlink()
    with pytest.raises(CorruptSegment):
        Engine(tmp_path / "index").search(Principal("t", "r"), "valid")
    with catalog.connection() as connection:
        connection.execute("UPDATE state SET tokenizer='unknown'")
    with pytest.raises(ValueError):
        Catalog(tmp_path / "index", "t")


def test_stale_merge_rejects_concurrent_publication(tmp_path, monkeypatch):
    from pp_atlas import engine as module

    writer, merger = Engine(tmp_path), Engine(tmp_path)
    writer.upsert("t", Document("a", "a", "first"))
    original = module.write_segment

    def interleave(directory, records):
        result = original(directory, records)
        monkeypatch.setattr(module, "write_segment", original)
        writer.upsert("t", Document("b", "b", "second"))
        return result

    monkeypatch.setattr(module, "write_segment", interleave)
    with pytest.raises(RuntimeError, match="generation changed"):
        merger.merge("t")
    assert Engine(tmp_path).search(Principal("t", "r"), "").total == 2


def test_cache_is_bounded_and_filter_cannot_include_hidden(tmp_path):
    cache = LRU[int](1)
    cache.put(("a",), 1)
    cache.put(("b",), 2)
    assert cache.get(("a",)) is None and cache.get(("b",)) == 2
    engine = Engine(tmp_path)
    engine.upsert("../../escape", Document("../document", "x", "text", frozenset({"user:bob"})))
    assert engine.search(Principal("../../escape", "alice"), "id:../document").total == 0
    assert len(list(tmp_path.iterdir())) == 1
    assert next(tmp_path.iterdir()).name.isalnum()
    with pytest.raises(ValueError):
        Catalog(tmp_path, "")
    with pytest.raises(ValueError):
        engine.set_groups("t", "r", [""])
    with pytest.raises(ValueError):
        Document("x", "", "", frozenset(str(i) for i in range(129)))
    with pytest.raises(ValueError):
        Document("x", "", "", metadata={"x": "z" * 4097})


def test_returned_records_cannot_poison_search_cache(tmp_path):
    engine = Engine(tmp_path)
    engine.upsert("t", Document("a", "a", "word"))
    principal = Principal("t", "r")
    result = engine.search(principal, "word")
    expected = result.hits[0].score
    result.facets["forged"] = 100
    result.statistics["N"] = -1
    result.hits[0].explanation["word"] = -1
    second = engine.search(principal, "word")
    assert "forged" not in second.facets
    assert second.statistics["N"] == 1
    assert second.hits[0].explanation["word"] == expected
    second.facets["forged-again"] = 100
    assert "forged-again" not in engine.search(principal, "word").facets
