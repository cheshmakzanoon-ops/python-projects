"""An idle unfinished input may still resume after the other input has ended."""

import json

import pytest

from pp_current import Config, Engine, Record, canonical
from pp_current.event_time.policy import MAX_TIME


def test_last_active_end_does_not_finalize_an_unfinished_idle_input() -> None:
    config = Config((canonical(["a", 0]), canonical(["b", 0])), size=10, slide=5, lateness=2)
    engine = Engine(config)

    def apply(
        source: str, offset: int, timestamp: int = 0, kind: str = "event", value: int = 1
    ) -> str:
        return engine.apply(
            Record(
                source,
                0,
                offset,
                timestamp,
                "key",
                value,
                kind=kind,
                ingress_ordinal=engine.position + 1,
            )
        )  # type: ignore[arg-type]

    apply("a", 0, 1, value=3)
    apply("a", 1, 10, "watermark")
    apply("b", 0, kind="idle")
    assert engine.progress.watermark == 10
    apply("a", 2, kind="end")
    assert engine.progress.watermark == 10
    engine = Engine.restore(engine.dump(), config)
    apply("b", 1, kind="resume")
    assert apply("b", 2, 9, value=4) == "accepted-late"
    corrected = [delivery for delivery in engine.pending if delivery.operator_id == "tumbling"]
    assert len(corrected) == 1
    assert corrected[0].revision == 2
    assert json.loads(corrected[0].payload)["sum"] == 7
    assert apply("b", 3, 20, value=5) == "on-time"
    apply("b", 4, kind="end")
    assert engine.progress.watermark == MAX_TIME
    assert not engine.state and not engine.join


def test_premature_terminal_checkpoint_requires_replay_from_raw_ingress() -> None:
    config = Config((canonical(["a", 0]), canonical(["b", 0])))
    engine = Engine(config)
    data = json.loads(engine.dump())
    data.update(
        position=2,
        watermarks={config.inputs[0]: MAX_TIME, config.inputs[1]: -(2**63)},
        idle=[config.inputs[1]],
        watermark=MAX_TIME,
    )
    with pytest.raises(ValueError, match="terminal"):
        Engine.restore(canonical(data), config)
