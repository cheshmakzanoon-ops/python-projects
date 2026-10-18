from dataclasses import replace

import pytest

from pp_current import Config, Engine, Record, canonical
from pp_current.operators.tumbling import windows
from pp_current.runtime.engine import CODE_VERSION

INPUT = canonical(["s", 0])


def apply(engine: Engine, **kwargs: object) -> str:
    return engine.apply(
        Record("s", 0, engine.position, ingress_ordinal=engine.position + 1, **kwargs)
    )  # type: ignore[arg-type]


def test_boundaries_revisions_and_no_resurrection() -> None:
    engine = Engine(Config((INPUT,), size=10, slide=5, lateness=3, join_interval=2))
    assert windows(-1, 10, 5) == [-5, -10]
    apply(engine, event_time=-1, value=7)
    apply(engine, event_time=0, value=10)
    apply(engine, kind="watermark", event_time=10)
    first = [
        d for d in engine.pending if d.operator_id == "tumbling" and "0,10" in d.logical_result_key
    ]
    assert len(first) == 1 and first[0].revision == 1
    assert apply(engine, event_time=7, value=2) == "accepted-late"  # exact lateness accepted
    revised = [
        d for d in engine.pending if d.operator_id == "tumbling" and "0,10" in d.logical_result_key
    ]
    assert revised[-1].revision == 2 and '"sum":12' in revised[-1].payload
    assert apply(engine, event_time=6) == "rejected-late"
    apply(engine, kind="watermark", event_time=100)
    assert apply(engine, event_time=7) == "rejected-late"
    assert not engine.state and not engine.join


def test_join_inclusive_boundaries_empty_keys_and_duplicate_event_ids() -> None:
    engine = Engine(Config((INPUT,), size=10, slide=5, join_interval=2))
    apply(engine, event_time=-1, value=3, event_id="same")
    apply(engine, event_time=-1, value=3, event_id="same")
    apply(engine, event_time=1, stream="metadata", payload="a")
    apply(engine, event_time=2, stream="metadata", payload="b")
    joined = [d for d in engine.pending if d.operator_id == "interval-join"]
    assert len(joined) == 2
    assert all('"delta_ms":2' in d.payload for d in joined)


def test_idle_resume_and_regressions() -> None:
    other = canonical(["s", 1])
    engine = Engine(Config((INPUT, other), size=10, slide=5, lateness=3))
    apply(engine, kind="watermark", event_time=30)
    assert engine.progress.watermark < 0
    record = Record("s", 1, 0, kind="idle", ingress_ordinal=2)
    engine.apply(record)
    assert engine.progress.watermark == 30
    engine.apply(replace(record, kind="resume", source_offset=1, ingress_ordinal=3))
    assert engine.progress.watermark == 30
    assert (
        engine.apply(
            replace(record, kind="event", source_offset=2, event_time=1, ingress_ordinal=4)
        )
        == "rejected-late"
    )
    with pytest.raises(ValueError, match="regression"):
        apply(engine, kind="watermark", event_time=29)


def test_restore_compatibility_and_stable_partition() -> None:
    from pp_current import partition_for

    engine = Engine(Config((INPUT,)))
    apply(engine, event_time=2, value=1)
    assert Engine.restore(engine.dump(), engine.config).dump() == engine.dump()
    with pytest.raises(ValueError, match="incompatible"):
        Engine.restore(engine.dump().replace(CODE_VERSION, "current-99"), engine.config)
    with pytest.raises(ValueError, match="incompatible"):
        Engine.restore(engine.dump(), replace(engine.config, workers=2))
    assert partition_for("", 4) == 0


def test_end_of_idle_input_finalizes_windows_and_survives_restore() -> None:
    engine = Engine(Config((INPUT,), size=10, slide=5))
    apply(engine, event_time=1, value=7)
    apply(engine, kind="idle")
    engine = Engine.restore(engine.dump(), engine.config)
    apply(engine, kind="end")
    assert not engine.state and not engine.join
    assert engine.progress.watermark == 2**63 - 1
    assert len(engine.pending) == 3
    assert INPUT not in engine.progress.idle


@pytest.mark.parametrize("kind", ["event", "idle", "resume", "watermark"])
def test_ended_input_cannot_reopen_while_other_input_is_pending(kind: str) -> None:
    other = canonical(["s", 1])
    engine = Engine(Config((INPUT, other)))
    apply(engine, kind="end")
    with pytest.raises(ValueError, match="ended"):
        apply(engine, kind=kind)
    assert engine.position == 1
