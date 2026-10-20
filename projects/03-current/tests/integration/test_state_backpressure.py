"""Resource budgets constrain allocation and can be adjusted without changing semantics."""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from pp_current import Config, Engine, Journal, Record, Runtime, canonical

INPUT = canonical(["s", 0])


def test_sliding_fanout_reserves_state_before_allocating_each_window() -> None:
    engine = Engine(Config((INPUT,), size=20_000, slide=1, state_limit=3))
    with pytest.raises(MemoryError):
        engine.apply(Record("s", 0, 0, ingress_ordinal=1))
    assert len(engine.state) + engine.join_count <= 3
    with pytest.raises(RuntimeError, match="recover"):
        engine.dump()


def test_state_budget_increase_resumes_the_last_committed_prefix(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "increase.db")
    config = Config((INPUT,), size=10, slide=5, state_limit=4, join_interval=2, lateness=2)
    try:
        journal.admit([Record("s", 0, 0, 1, "one", 2)])
        asyncio.run(Runtime(journal, journal.recover(config)).run())
        journal.admit([Record("s", 0, 1, 2, "one", 3), Record("s", 0, 2, kind="end")])
        with pytest.raises(ExceptionGroup):
            asyncio.run(Runtime(journal, journal.recover(config)).run())
        assert journal.recover(config).position == 1
        larger = replace(config, state_limit=8)
        asyncio.run(Runtime(journal, journal.recover(larger)).run())
        assert journal.recover(larger).position == 3
        assert all(row["payload"]["sum"] == 5 for row in journal.export())  # type: ignore[index]
    finally:
        journal.close()


def test_current_retained_state_not_historical_peak_controls_a_lower_budget(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "decrease.db")
    config = Config((INPUT,), size=10, slide=5, state_limit=4, join_interval=2, lateness=2)
    try:
        journal.admit([Record("s", 0, 0, 1, "one", 2), Record("s", 0, 1, 100, kind="watermark")])
        asyncio.run(Runtime(journal, journal.recover(config)).run())
        smaller = replace(config, state_limit=1)
        restored = journal.recover(smaller)
        assert restored.peak_state == 4
        assert not restored.state and not restored.join
        journal.admit([Record("s", 0, 2, 100, "one", stream="metadata")])
        asyncio.run(Runtime(journal, restored).run())
        assert journal.recover(smaller).peak_state == 4
        assert journal.recover(smaller).join_count == 1
        with pytest.raises(ValueError):
            journal.recover(replace(smaller, size=20))
    finally:
        journal.close()
