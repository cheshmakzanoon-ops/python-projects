"""Benchmark accounting must include the separate hot workload's memory peak."""

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from pp_current import cli


@pytest.mark.parametrize("profile", [cli.Profile.ci, cli.Profile.standard])
def test_rss_sample_includes_hot_workload_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: cli.Profile
) -> None:
    events: list[str] = []
    peak_kib = 100
    original_clean = cli.clean_demo

    def execute(
        output: Path, count: int, seed: int, *, hot: bool = False, oracle: bool = True
    ) -> dict[str, object]:
        nonlocal peak_kib
        cli.owned(output)
        events.append(f"execute:{output.name}")
        if hot:
            peak_kib = 1000
        return {"throughput_events_s": 1.0, "oracle_matches": True}

    def clean(output: Path) -> None:
        events.append(f"cleanup:{output.name}")
        original_clean(output)

    def getrusage(who: int) -> SimpleNamespace:
        events.append("rss_sample")
        return SimpleNamespace(ru_maxrss=peak_kib)

    resource = ModuleType("resource")
    monkeypatch.setattr(resource, "RUSAGE_SELF", 0, raising=False)
    monkeypatch.setattr(resource, "getrusage", getrusage, raising=False)
    monkeypatch.setitem(sys.modules, "resource", resource)
    monkeypatch.setattr(cli, "execute", execute)
    monkeypatch.setattr(cli, "clean_demo", clean)
    monkeypatch.setattr(cli, "provenance", lambda seed, profile: {"source_content_sha256": "fixed"})

    output = tmp_path / profile.value
    cli.benchmark(output=output, profile=profile, seed=1729)

    result = json.loads((output / "benchmark.json").read_text())
    assert result["metrics"]["peak_process_rss_bytes"] == 1000 * 1024
    assert events.index("rss_sample") > events.index("execute:hot")
    if profile == cli.Profile.standard:
        assert events.index("rss_sample") > events.index("cleanup:hot")
    assert events.count("rss_sample") == 1
