"""Full-prefix output revisions against an intentionally unindexed two-input model."""

from typing import Literal

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_current import Config, Engine, Record, canonical
from tests.reference_trace import TraceModel

Kind = Literal["event", "watermark", "idle", "resume", "end"]


Action = tuple[int, Kind, int, int, str, bool]


@settings(max_examples=65, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(0, 1),
            st.sampled_from(["event", "event", "event", "watermark", "idle", "resume"]),
            st.integers(-30, 50),
            st.integers(-9, 9),
            st.sampled_from(["", "one", "two"]),
            st.booleans(),
        ),
        min_size=1,
        max_size=55,
    ),
    st.sampled_from([0, 1, 3, 7]),
)
def test_every_output_revision_survives_arbitrary_controls_and_restores(
    actions: list[Action], interval: int
) -> None:
    config = Config(
        (canonical(["a", 0]), canonical(["b", 0])),
        size=12,
        slide=4,
        lateness=8,
        join_interval=interval,
    )
    engine = Engine(config, "trace")
    model = TraceModel(config)
    offsets = [0, 0]
    seen: set[tuple[str, str, str, int]] = set()

    def step(source: int, kind: Kind, timestamp: int, value: int, key: str, metadata: bool) -> None:
        nonlocal engine
        record = Record(
            "ab"[source],
            0,
            offsets[source],
            timestamp,
            key,
            value,
            "metadata" if metadata else "reading",
            kind=kind,
            payload=str(value),
            ingress_ordinal=engine.position + 1,
        )
        offsets[source] += 1
        expected_status, expected_output = model.apply(record)
        assert engine.apply(record) == expected_status
        actual = {delivery.identity: delivery.payload for delivery in engine.pending}
        assert len(actual) == len(engine.pending)
        assert actual == {delivery.identity: delivery.payload for delivery in expected_output}
        assert not set(actual) & seen
        seen.update(actual)
        engine.pending.clear()
        assert engine.progress.watermark == model.watermark
        assert engine.dispositions == {
            name: model.dispositions[name] for name in engine.dispositions
        }
        if engine.position % 7 == 0:
            saved = engine.dump()
            engine = Engine.restore(saved, config)
            assert engine.dump() == saved

    for source, kind, timestamp, value, key, metadata in actions:
        identity = config.inputs[source]
        if kind == "event" and identity in model.inactive:
            step(source, "resume", 0, 0, "", False)
        if kind == "watermark":
            timestamp = max(timestamp, model.clocks[identity])
        step(source, kind, timestamp, value, key, metadata)
    step(0, "end", 0, 0, "", False)
    step(1, "end", 0, 0, "", False)
    assert not engine.state and not engine.join
