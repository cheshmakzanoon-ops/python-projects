"""Playable self-contained report with authentic plots and explicit uncertainty."""

import base64
import html
import io
import json
from dataclasses import asdict
from pathlib import Path

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
    plt.close(fig)
    image = base64.b64encode(buffer.getvalue()).decode()
    audio_data = base64.b64encode(audio_path.read_bytes()).decode()
    rows = "".join(
        f"<tr><td>{html.escape(n.id)}</td><td>{n.midi}</td><td>{n.start / rate:.3f}</td>"
        f"<td>{n.end / rate:.3f}</td><td>{n.cents:+.2f}</td>"
        f"<td>{n.confidence:.3f}</td><td>{n.spread_cents:.1f}</td></tr>"
        for n in report.notes
    )
    diagnostics = "".join(f"<li>{html.escape(d)}</li>" for d in report.diagnostics)
    trajectory = [(p.center / rate, p.frequency, p.confidence) for p in report.pitches]
    path.write_text(f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Resonance analysis</title><style>body{{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:1rem;background:#faf9f6;color:#173a35}}img{{width:100%}}td,th{{padding:.4rem;text-align:right}}audio{{width:100%}}details{{margin:1rem 0}}</style>
<h1>Resonance · listen, inspect, compare</h1><p>Offline monophonic analysis. Confidence is periodicity evidence, not a probability of musical correctness. Synthetic performance does not establish accuracy on real guitar recordings.</p>
<audio controls src="data:audio/wav;base64,{audio_data}"></audio>
<p><a href="transcription.mid" download>Download MIDI</a> · <a href="analysis.json">Analysis JSON</a></p>
<img alt="Actual waveform, spectrogram and estimated versus reference notes" src="data:image/png;base64,{image}">
<ul>{diagnostics}</ul><p>Wide pitch spread can reflect bends or vibrato; median intonation does not judge artistic intention. Unvoiced frames are retained in JSON.</p>
<table><tr><th>Note</th><th>MIDI</th><th>Start s</th><th>End s</th><th>Cents</th><th>Confidence</th><th>90–10% spread ¢</th></tr>{rows}</table>
<details><summary>Source and numerical provenance</summary><pre>{html.escape(json.dumps(provenance, indent=2))}</pre></details>
<details><summary>Alignment (extra/missing notes stay explicit)</summary><pre>{html.escape(json.dumps([asdict(a) for a in report.alignment], indent=2))}</pre></details>
<script type="application/json" id="pitch-trajectory">{json.dumps(trajectory)}</script>
</html>""")
    # Keep a small independently viewable actual figure alongside the HTML.
    (path.parent / "analysis.png").write_bytes(buffer.getvalue())
