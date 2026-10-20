from html.parser import HTMLParser
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

from pp_resonance.analysis import analyze
from pp_resonance.audio_io.pcm import write
from pp_resonance.model import NoteEvent
from pp_resonance.reports.render import render


class Elements(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("include_note", [False, True])
def test_report_is_accessible_and_escapes_external_metadata(
    tmp_path: Path, include_note: bool
) -> None:
    samples = np.zeros(4800, dtype=np.float64)
    audio = tmp_path / "audio.wav"
    write(audio, samples, 48000)
    report = analyze(samples, 48000)
    report.sample_count = 96000  # Rendering an excerpt from a longer analysis.
    report.diagnostics.append('<script>alert("recording")</script>')
    if include_note:
        report.notes = [NoteEvent('<img src=x onerror="alert(1)">', 60, 0, 4800, 261.6, 1, 0)]
    output = tmp_path / "analysis.html"
    render(output, report, audio, samples, [], {"source": "<script>unsafe</script>"})
    document = output.read_text(encoding="utf-8")
    elements = Elements()
    elements.feed(document)
    assert (
        "meta",
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    ) in elements.tags
    assert any(tag == "main" and attrs.get("id") == "content" for tag, attrs in elements.tags)
    assert any(
        tag == "audio"
        and attrs.get("aria-label") == "Recording audio"
        and attrs.get("aria-describedby") == "playback-scope"
        for tag, attrs in elements.tags
    )
    assert sum(tag == "th" and attrs.get("scope") == "col" for tag, attrs in elements.tags) == 7
    assert any(tag == "caption" for tag, _ in elements.tags)
    assert any(
        tag == "div" and attrs.get("role") == "region" and attrs.get("tabindex") == "0"
        for tag, attrs in elements.tags
    )
    assert "First 0.1 seconds of a 2.0-second recording" in document
    assert "the note table, JSON and MIDI cover the full recording" in document
    assert "<script>alert" not in document and "<script>unsafe" not in document
    assert all(
        attrs.get("type") == "application/json" for tag, attrs in elements.tags if tag == "script"
    )
    if include_note:
        assert "&lt;img src=x onerror=" in document
        assert any(tag == "th" and attrs.get("scope") == "row" for tag, attrs in elements.tags)
    else:
        assert "No confident sustained notes were detected." in document
    assert (tmp_path / "analysis.png").read_bytes().startswith(b"\x89PNG")


def test_failed_report_plot_releases_its_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matplotlib.figure import Figure

    report = analyze(np.zeros(4800, dtype=np.float64), 48000)
    write(tmp_path / "audio.wav", np.zeros(4800), 48000)
    before = plt.get_fignums()

    def fail_save(*args: object, **kwargs: object) -> None:
        raise OSError("plot output unavailable")

    monkeypatch.setattr(Figure, "savefig", fail_save)
    with pytest.raises(OSError, match="unavailable"):
        render(tmp_path / "analysis.html", report, tmp_path / "audio.wav", np.zeros(4800), [], {})
    assert plt.get_fignums() == before


def test_installed_provenance_includes_the_report_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pp_resonance import provenance

    package = tmp_path / "lib" / "site-packages" / "pp_resonance"
    package.mkdir(parents=True)
    module = package / "provenance.py"
    module.write_text("# installed module\n")
    template = package / "reports" / "analysis.html"
    template.parent.mkdir()
    template.write_text("<h1>Original</h1>")
    monkeypatch.setattr(provenance, "__file__", str(module))
    first = provenance.metadata(1729, "demo")
    assert "reports/analysis.html" in first["source_inputs"]
    template.write_text("<h1>Changed</h1>")
    assert (
        first["source_content_sha256"] != provenance.metadata(1729, "demo")["source_content_sha256"]
    )
