"""Directed stream/time indexing must preserve inclusive pair identities and order."""

import json

import pytest

from pp_current import Config, Engine, Record, canonical


@pytest.mark.parametrize("interval", [0, 1, 2, 7])
def test_sparse_cross_stream_probe_does_not_scan_hot_same_stream_history(interval: int) -> None:
    config = Config((canonical(["s", 0]),), size=100_000, slide=100_000, join_interval=interval)
    engine = Engine(config)
    count = 3000
    for offset in range(count):
        engine.apply(
            Record("s", 0, offset, offset - count // 2, "hot", 1, ingress_ordinal=offset + 1)
        )
    assert engine.join_candidates_examined == 0
    engine = Engine.restore(engine.dump(), config)
    engine.apply(Record("s", 0, count, -2, "hot", stream="metadata", ingress_ordinal=count + 1))
    joined = [json.loads(delivery.payload)["reading_ordinal"] for delivery in engine.pending]
    expected = [offset + 1 for offset in range(count) if abs(offset - count // 2 + 2) <= interval]
    assert joined == expected
    assert engine.join_candidates_examined <= 3 * (interval + 1)


def test_expiration_rebuilds_the_index_without_reintroducing_expired_records() -> None:
    config = Config((canonical(["s", 0]),), size=10, slide=5, lateness=2, join_interval=2)
    engine = Engine(config)
    trace = [
        Record("s", 0, 0, -5, "hot"),
        Record("s", 0, 1, 5, "hot"),
        Record("s", 0, 2, 9, kind="watermark"),
        Record("s", 0, 3, 7, "hot", stream="metadata"),
    ]
    for ordinal, record in enumerate(trace, 1):
        from dataclasses import replace

        engine.apply(replace(record, ingress_ordinal=ordinal))
    pairs = [
        json.loads(delivery.payload)
        for delivery in engine.pending
        if delivery.operator_id == "interval-join"
    ]
    assert len(pairs) == 1
    assert pairs[0]["reading_ordinal"] == 2
    assert pairs[0]["metadata_ordinal"] == 4
    assert engine.join_count == 2
