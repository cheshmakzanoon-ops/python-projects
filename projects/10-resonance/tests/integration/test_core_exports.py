"""Verify encoded playback and MIDI with independent decoders and timing arithmetic."""

import base64
import hashlib
import io
import json
import random
import re
from fractions import Fraction
from pathlib import Path

import matplotlib.pyplot as plt
import mido
import numpy as np
import pytest
import soundfile as sf

from pp_resonance.analysis import analyze
from pp_resonance.cli import prepare, save_demo
from pp_resonance.midi.export import check_bytes, export
from pp_resonance.model import NoteEvent
from pp_resonance.reports.render import render


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("tempo", [333333, 500000, 500001, 900000])
@pytest.mark.parametrize("seed", range(4))
def test_midi_timing_against_exact_rational_seconds(
    tmp_path: Path, rate: int, tempo: int, seed: int
) -> None:
    rng = random.Random(seed)
    notes, position = [], 0
    for i in range(12):
        start = position + rng.randrange(2000)
        position = start + rng.randrange(3000, 16000)
        notes.append(NoteEvent(f"n{i}", 60 + i % 3, start, position, 440, 1, 0))
    path = tmp_path / "timing.mid"
    export(path, notes, rate, tempo)
    # mido's parser is independent of the product's byte checker. Recover ticks
    # directly, and bound reconstructed seconds using exact rational arithmetic.
    midi = mido.MidiFile(path)
    assert midi.ticks_per_beat == 480
    absolute, active, observed, declared_tempo = 0, {}, [], None
    for event in midi.tracks[0]:
        absolute += event.time
        if event.type == "set_tempo":
            declared_tempo = event.tempo
        elif event.type == "note_on" and event.velocity:
            assert event.note not in active
            active[event.note] = absolute
        elif event.type == "note_off" or event.type == "note_on":
            observed.append((event.note, active.pop(event.note), absolute))
    assert not active and declared_tempo == tempo
    assert observed == check_bytes(path)
    half_tick = Fraction(tempo, 2 * 480 * 1_000_000)
    for (pitch, start_tick, end_tick), expected in zip(observed, notes, strict=True):
        assert pitch == expected.midi
        for tick, sample in ((start_tick, expected.start), (end_tick, expected.end)):
            reconstructed = Fraction(tick * tempo, 480 * 1_000_000)
            assert abs(reconstructed - Fraction(sample, rate)) <= half_tick


def test_report_rejects_playback_that_does_not_match_the_figure(tmp_path: Path) -> None:
    samples = np.zeros(4800)
    path = tmp_path / "audio.wav"
    sf.write(path, samples, 48000, subtype="PCM_16")
    report = analyze(samples, 48000)
    before = plt.get_fignums()
    output = tmp_path / "analysis.html"
    with pytest.raises(ValueError, match="match the embedded"):
        render(output, report, path, np.ones(4800), [], {})
    assert not output.exists() and plt.get_fignums() == before


def test_demo_embedded_audio_and_json_have_the_same_playback_provenance(tmp_path: Path) -> None:
    output = prepare(tmp_path / "demo")
    save_demo(output, 1729)
    data = json.loads((output / "analysis.json").read_text())
    document = (output / "analysis.html").read_text()
    match = re.search(r'data:audio/wav;base64,([^"\s]+)', document)
    assert match is not None
    embedded = base64.b64decode(match.group(1), validate=True)
    playback = data["provenance"]["playback"]
    assert playback["sha256"] == hashlib.sha256(embedded).hexdigest()
    assert embedded == (output / "audio.wav").read_bytes()
    audio, rate = sf.read(io.BytesIO(embedded), dtype="float64")
    assert playback == {
        "sha256": hashlib.sha256(embedded).hexdigest(),
        "sample_rate": rate,
        "sample_count": len(audio),
        "scope": "full",
    }
    assert len(audio) == data["sample_count"]
