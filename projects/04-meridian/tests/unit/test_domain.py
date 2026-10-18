from datetime import datetime, timezone
from itertools import product
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.domain.money import MAX_AMOUNT, allocate, parse_amount
from pp_meridian.domain.replay import HistoricalPosting, replay, trial_balance
from pp_meridian.reconciliation.assignment import ComponentTooLarge, solve, solve_component
from pp_meridian.reconciliation.candidates import Edge, MatchEntry, candidates
from pp_meridian.reconciliation.normalize import normalize_row


def test_exact_decimal_and_rejections():
    assert parse_amount("1.23", "USD") == 123
    assert parse_amount("-0.001", "KWD") == -1
    assert parse_amount("10", "JPY") == 10
    for value in [1.2, True, "NaN", "inf", "01.20", "+1", "1e2", "1.234", " 1.00"]:
        with pytest.raises(ValueError):
            parse_amount(value, "USD")
    with pytest.raises(ValueError):
        parse_amount("1", "XXX")
    with pytest.raises(ValueError):
        parse_amount(str(MAX_AMOUNT), "USD")


def test_largest_remainder_ties_negative():
    assert allocate(1, (1, 1, 1)) == (1, 0, 0)
    assert allocate(-1, (1, 1, 1)) == (-1, 0, 0)
    assert allocate(10, (1, 2, 3)) == (2, 3, 5)
    for weights in [(), (0, 0), (-1, 2), (True, 1)]:
        with pytest.raises(ValueError):
            allocate(1, weights)


@given(
    st.integers(-(10**12), 10**12),
    st.lists(st.integers(0, 10000), min_size=1, max_size=30).filter(lambda w: sum(w) > 0),
)
def test_allocation_conservation(total, weights):
    result = allocate(total, tuple(weights))
    assert sum(result) == total
    assert all(
        abs(a * sum(weights) - abs(total) * w) < sum(weights)
        for a, w in zip(map(abs, result), weights)
    )
    assert result == tuple(-x for x in allocate(-total, tuple(weights)))


def test_journal_and_replay():
    a, b, t = uuid4(), uuid4(), uuid4()
    value = JournalValue(t, "USD", (Entry(a, 20), Entry(b, -20)))
    value.validate()
    assert value.reversed().entries[0].amount == -20
    for entries in [
        (Entry(a, 1),),
        (Entry(a, 1), Entry(b, -2)),
        (Entry(a, 0), Entry(b, 0)),
        (Entry(a, 1), Entry(a, -1)),
    ]:
        with pytest.raises(ValueError):
            JournalValue(t, "USD", entries).validate()
    rows = [
        HistoricalPosting(a, "USD", 20, 1),
        HistoricalPosting(b, "USD", -20, 1),
        HistoricalPosting(a, "USD", -3, 2),
        HistoricalPosting(b, "USD", 3, 2),
    ]
    assert replay(rows, 1) == {a: 20, b: -20}
    assert replay(rows) == {a: 17, b: -17}
    assert trial_balance(rows) == {"USD": 0}


def exhaustive(left, edges, unmatched=250):
    choices = [[None] + [e.right for e in edges if e.left == left_id] for left_id in left]
    scores = []
    costs = {(e.left, e.right): e.cost for e in edges}
    for selected in product(*choices):
        rights = [r for r in selected if r is not None]
        if len(rights) != len(set(rights)):
            continue
        scores.append(
            sum(unmatched if r is None else costs[left_id, r] for left_id, r in zip(left, selected))
        )
    best = min(scores)
    return best, scores.count(best) > 1


@given(st.lists(st.integers(0, 300), min_size=9, max_size=9))
def test_solver_against_exhaustive(costs):
    left = ["a", "b", "c"]
    edges = [
        Edge(left_id, str(j), costs[i * 3 + j]) for i, left_id in enumerate(left) for j in range(3)
    ]
    result = solve_component(left, edges)
    assert (result.cost, result.ambiguous) == exhaustive(left, edges)


def test_ambiguous_and_component_bounds():
    edges = [Edge("a", "1", 0), Edge("a", "2", 0), Edge("b", "1", 0), Edge("b", "2", 0)]
    assert solve_component(["a", "b"], edges).ambiguous
    assert solve_component(["a"], [Edge("a", "1", 250)]).ambiguous
    assert len(solve([str(i) for i in range(100)], [])) == 100
    with pytest.raises(ComponentTooLarge):
        solve_component([str(i) for i in range(33)], [])
    with pytest.raises(ComponentTooLarge):
        solve_component(["a"], [Edge("a", str(i), 1) for i in range(257)])
    with pytest.raises(ValueError):
        solve_component(["a"], [Edge("b", "1", 0)])


def test_normalization_direction_timezone_and_candidates():
    raw = {
        "id": "1",
        "amount": "-1.00",
        "currency": "USD",
        "timestamp": "2026-01-01T01:00:00+01:00",
        "reference": " inv-12 ",
    }
    row = normalize_row(raw)
    assert row.amount == -100 and row.timestamp.hour == 0 and row.reference == "INV12"
    assert (
        normalize_row(
            {**raw, "timestamp": "2026-01-01T00:00:00Z", "reference": "INV12"}
        ).payload_hash
        == row.payload_hash
    )
    with pytest.raises(ValueError):
        normalize_row({**raw, "timestamp": "2026-01-01"})
    now = datetime.now(timezone.utc)
    a = MatchEntry("a", 100, "USD", now, "INV1")
    assert candidates([a], [MatchEntry("b", 100, "USD", now, "inv-1")]) == [Edge("a", "b", 0)]
    assert candidates([a], [MatchEntry("b", -100, "USD", now, "")]) == []


@pytest.mark.parametrize("timestamp", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_statement_timestamp_outside_utc_range_is_a_validation_error(timestamp):
    with pytest.raises(ValueError, match="supported UTC range"):
        normalize_row(
            {
                "id": "boundary",
                "amount": "1.00",
                "currency": "USD",
                "timestamp": timestamp,
                "reference": "",
            }
        )


@pytest.mark.parametrize(
    "instant",
    [datetime.min.replace(tzinfo=timezone.utc), datetime.max.replace(tzinfo=timezone.utc)],
)
def test_candidate_date_window_is_clipped_at_representable_boundaries(instant):
    row = MatchEntry("row", 100, "USD", instant, "same")
    posting = MatchEntry("posting", 100, "USD", instant, "same")
    assert candidates([row], [posting]) == [Edge("row", "posting", 0)]
    assert candidates([row], []) == []


def test_candidate_construction_enforces_bounds_before_dense_graph_growth():
    now = datetime.now(timezone.utc)
    rows = [MatchEntry(str(i), 100, "USD", now, "") for i in range(33)]
    postings = [MatchEntry(str(i), 100, "USD", now, "") for i in range(300)]
    with pytest.raises(ComponentTooLarge):
        candidates(rows, postings)
    with pytest.raises(ValueError):
        candidates([], [], days=32)
    assert candidates(rows[:1], postings[:256])


def test_regression_unmatched_edge_ambiguity_with_other_fixed_matches():
    costs = [0, 0, 2, 249, 66, 250, 183, 0, 185]
    edges = [
        Edge(key, str(j), costs[i * 3 + j])
        for i, key in enumerate(["a", "b", "c"])
        for j in range(3)
    ]
    result = solve_component(["a", "b", "c"], edges)
    assert result.cost == 250 and result.ambiguous


def test_invalid_normalized_rows_and_domain_bounds():
    raw = {
        "id": "row",
        "amount": "1.00",
        "currency": "USD",
        "timestamp": "2026-01-01T00:00:00Z",
        "reference": "ref",
    }
    for changed in [{"id": 1}, {"id": ""}, {"amount": "0.00"}, {"reference": "r" * 201}]:
        with pytest.raises(ValueError):
            normalize_row({**raw, **changed})
    with pytest.raises(ValueError):
        allocate(True, (1,))
    with pytest.raises(ValueError):
        JournalValue(uuid4(), "XXX", (Entry(uuid4(), 1), Entry(uuid4(), -1))).validate()
    with pytest.raises(ValueError):
        JournalValue(uuid4(), "USD", (Entry(uuid4(), 1), Entry(uuid4(), -1)), "r" * 201).validate()
    with pytest.raises(ValueError):
        solve_component(["a", "a"], [])


def test_solver_exact_arbitrary_integer_costs_have_no_finite_infinity_collision():
    huge = 10**100
    result = solve_component(["row"], [], unmatched=huge)
    assert result.cost == huge and result.pairs == () and not result.ambiguous
    result = solve_component(["row"], [Edge("row", "posting", huge)], unmatched=huge)
    assert result.cost == huge and result.ambiguous
    result = solve_component(
        ["a", "b"], [Edge("a", "one", huge - 1), Edge("b", "two", huge - 2)], unmatched=huge
    )
    assert result.cost == 2 * huge - 3 and not result.ambiguous
    for bad in [True, 1.5, float("nan")]:
        with pytest.raises(ValueError):
            solve_component(["row"], [], unmatched=bad)
        with pytest.raises(ValueError):
            solve_component(["row"], [Edge("row", "posting", bad)])
