from dataclasses import asdict, replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pp_current import Config, Engine, Record, canonical
from pp_current.diagnostics.oracle import reconcile


@given(
    st.lists(
        st.tuples(
            st.integers(-50, 80),
            st.integers(-20, 20),
            st.sampled_from(["", "x", "y"]),
            st.booleans(),
        ),
        min_size=1,
        max_size=60,
    )
)
@settings(max_examples=80, deadline=None)
def test_raw_trace_against_independent_batch_oracle(
    events: list[tuple[int, int, str, bool]],
) -> None:
    config = Config((canonical(["s", 0]),), size=10, slide=5, lateness=15, join_interval=3)
    engine = Engine(config)
    trace = []
    maximum = -100
    for timestamp, value, key, metadata in events:
        record = Record(
            "s", 0, len(trace), timestamp, key, value, stream="metadata" if metadata else "reading"
        )
        trace.append(replace(record, ingress_ordinal=len(trace) + 1))
        maximum = max(maximum, timestamp)
        trace.append(
            Record(
                "s", 0, len(trace), maximum - 10, kind="watermark", ingress_ordinal=len(trace) + 1
            )
        )
    trace.append(Record("s", 0, len(trace), kind="end", ingress_ordinal=len(trace) + 1))
    actual_dispositions = [engine.apply(record) for record in trace]
    expected_dispositions, expected = reconcile(
        [asdict(record) for record in trace],
        inputs=config.inputs,
        size=10,
        slide=5,
        lateness=15,
        interval=3,
    )
    latest = {}
    import json

    for delivery in engine.pending:
        latest[delivery.operator_id + ":" + delivery.logical_result_key] = json.loads(
            delivery.payload
        )
    assert actual_dispositions == expected_dispositions
    assert latest == expected
