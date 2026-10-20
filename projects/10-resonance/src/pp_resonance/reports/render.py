"""Playable self-contained report with authentic plots and explicit uncertainty."""

import base64
import html
import io
import json
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path
from string import Template

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pp_resonance.model import AnalysisReport, ReferenceNote, Samples


def report_json(report: AnalysisReport, provenance: dict[str, object]) -> dict[str, object]:
    return {
        **asdict(report),
        "provenance": provenance,
        "timing": {
            "authority": "integer sample positions",
            "frame_size": report.config.frame.size,
            "hop": report.config.frame.hop,
            "pitch_timestamp": "center",
            "lookahead_samples": report.config.frame.size,
        },
    }


def render(
    path: Path,
    report: AnalysisReport,
    audio_path: Path,
    audio: Samples,
    reference: list[ReferenceNote],
    provenance: dict[str, object],
) -> None:
    rate = report.sample_rate
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), constrained_layout=True, sharex=True)
    try:
        time = np.arange(len(audio)) / rate
        stride = max(1, len(audio) // 10000)
        axes[0].plot(time[::stride], audio[::stride], lw=0.5, color="#136f63")
        axes[0].set(ylabel="PCM amplitude", title="Resonance · monophonic audio")
        if len(audio) >= 2048:
            with np.errstate(divide="ignore"):
                axes[1].specgram(audio, NFFT=2048, Fs=rate, noverlap=1536, cmap="magma")
        axes[1].set(ylim=(60, 1800), ylabel="Frequency (Hz)")
        for note in (n for n in report.notes if n.start < len(audio)):
            axes[2].plot(
                [note.start / rate, note.end / rate],
                [note.midi + note.cents / 100] * 2,
                lw=4,
                alpha=max(0.2, note.confidence),
                color="#136f63",
            )
            axes[2].text(
                note.start / rate,
                note.midi + 0.25,
                f"{note.cents:+.1f}¢ / {note.confidence:.2f}",
                fontsize=7,
            )
        for ref in (r for r in reference if r.start < len(audio)):
            axes[2].plot(
                [ref.start / rate, ref.end / rate],
                [ref.midi] * 2,
                lw=1,
                color="#dd651d",
                linestyle="--",
            )
        for onset in (o for o in report.onsets if o.sample < len(audio)):
            for axis in axes:
                axis.axvline(onset.sample / rate, color="#b03a48", alpha=0.15, lw=0.5)
        axes[2].set(
            ylabel="MIDI + cents/100",
            xlabel="Time (seconds)",
            title="Detected notes (green), reference (orange); labels: cents / confidence",
        )
        axes[2].set_xlim(0, max(0.001, len(audio) / rate))
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130)
    finally:
        plt.close(fig)
    image = base64.b64encode(buffer.getvalue()).decode()
    audio_data = base64.b64encode(audio_path.read_bytes()).decode()
    rows = "".join(
        f'<tr><th scope="row">{html.escape(n.id)}</th><td>{n.midi}</td><td>{n.start / rate:.3f}</td>'
        f"<td>{n.end / rate:.3f}</td><td>{n.cents:+.2f}</td>"
        f"<td>{n.confidence:.3f}</td><td>{n.spread_cents:.1f}</td></tr>"
        for n in report.notes
    )
    if not rows:
        rows = '<tr><td colspan="7" class="empty">No confident sustained notes were detected.</td></tr>'
    diagnostics = "".join(f"<li>{html.escape(d)}</li>" for d in report.diagnostics)
    if not diagnostics:
        diagnostics = "<li>No additional recording diagnostics.</li>"
    trajectory = [(p.center / rate, p.frequency, p.confidence) for p in report.pitches]
    full_seconds = report.sample_count / rate
    preview_seconds = len(audio) / rate
    is_preview = len(audio) < report.sample_count
    playback_scope = (
        f"First {preview_seconds:.1f} seconds of a {full_seconds:.1f}-second recording. "
        "The figure follows this preview; the note table, JSON and MIDI cover the full recording."
        if is_preview
        else "Playback and figure cover the full recording."
    )
    voiced = sum(p.frequency is not None for p in report.pitches)
    voiced_percent = 100 * voiced / len(report.pitches) if report.pitches else 0
    template = Template(
        files("pp_resonance.reports").joinpath("analysis.html").read_text(encoding="utf-8")
    )
    document = template.substitute(
        duration=f"{full_seconds:.1f}",
        note_count=len(report.notes),
        voiced_percent=f"{voiced_percent:.1f}",
        sample_rate=f"{rate / 1000:g}",
        playback_scope=playback_scope,
        audio_data=audio_data,
        image=image,
        diagnostics=diagnostics,
        rows=rows,
        provenance=html.escape(json.dumps(provenance, indent=2)),
        alignment=html.escape(json.dumps([asdict(a) for a in report.alignment], indent=2)),
        trajectory=json.dumps(trajectory, allow_nan=False),
    )
    path.write_text(document, encoding="utf-8")
    # Keep a small independently viewable actual figure alongside the HTML.
    (path.parent / "analysis.png").write_bytes(buffer.getvalue())
