"""Timelines preserve verified durations, including delays at actual boundaries."""

from dataclasses import replace
from pathlib import Path

import pytest
from matplotlib.axes import Axes

from pp_routecraft import VehicleState, construct, prepare_replan, solve
from pp_routecraft.domain.instance import SearchBudget
from pp_routecraft.fixtures import new_request, tiny
from pp_routecraft.reporting.report import render


def _capture_bars(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple[tuple[int, int], ...]]]:
    bars: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    original = Axes.broken_barh

    def capture(self: Axes, xranges, yrange, **kwargs):
        bars.append((kwargs.get("facecolors"), tuple(xranges)))
        return original(self, xranges, yrange, **kwargs)

    monkeypatch.setattr(Axes, "broken_barh", capture)
    return bars


def test_completed_route_boundary_delay_is_not_reported_as_travel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = tiny()
    previous = replace(previous, vehicles=tuple(replace(v, end=100) for v in previous.vehicles))
    original = construct(previous)
    assert original is not None
    expanded = new_request(previous, original)
    completed = VehicleState(0, True, (1, 2, 3), 3, 20, 0, ())
    prepared = prepare_replan(previous, original, expanded, (completed, expanded.states[1]))
    result = solve(prepared, SearchBudget(0))
    assert result.plan is not None
    bars = _capture_bars(monkeypatch)
    render(prepared, result.plan, tmp_path)
    travel = [interval for color, intervals in bars if color == "#7da7d9" for interval in intervals]
    assert (20, 2) in travel  # actual departure 20; directed return 3 -> depot takes 2
    assert sum(duration for _, duration in travel) == result.plan.objective[1]
    assert "<svg" in (tmp_path / "timeline.svg").read_text()


def test_zero_duration_service_is_not_drawn_as_one_time_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = tiny()
    plan = construct(instance)
    assert plan is not None
    bars = _capture_bars(monkeypatch)
    render(instance, plan, tmp_path)
    service = [
        interval for color, intervals in bars if color == "#4caa79" for interval in intervals
    ]
    assert sum(duration for _, duration in service) == 0
