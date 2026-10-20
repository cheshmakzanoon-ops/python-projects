# Resonance

Resonance turns a monophonic guitar recording into a pitch trajectory, detected
notes and an optional reference-score alignment. The analysis implements
fixed-window YIN, adaptive spectral-flux onsets, confidence-aware note decoding
and monotone edit alignment. A playable HTML report presents the recorded audio
beside its waveform, spectrogram, note boundaries, cents offsets and uncertainty.

## Quick start

Run from `projects/10-resonance` with uv 0.12.23. The default is CPython 3.14.8;
CPython 3.13.16 is also tested. No GPU, microphone, account or network service is
required after installing dependencies.

```sh
uv sync --locked --python 3.14.8
uv run --locked resonance demo --output /tmp/resonance-demo --seed 1729
```

Open `/tmp/resonance-demo/analysis.html` in a browser. The demo analyzes six
synthetic guitar-like plucks and compares them to their known reference. Playback
uses the actual encoded PCM; it is not a reconstruction from estimated notes.
The output directory contains:

| File | Purpose |
| --- | --- |
| `analysis.html` | Responsive report with embedded audio, plots, diagnostics and note table |
| `analysis.json` | Full versioned trajectory, events, configuration and provenance |
| `analysis.png` | Standalone scientific figure |
| `transcription.mid` | Monophonic MIDI with explicit tempo and deterministic quantization |
| `audio.wav`, `reference.json` | Encoded signal and reference score |

Use an absolute output path. Empty directories are accepted; nonempty ones need
a matching Resonance ownership marker. Cleanup removes only known generated
files and preserves unrelated files:

```sh
uv run --locked resonance clean-demo --output /tmp/resonance-demo
```

## Analyze a recording

```sh
uv run --locked resonance analyze --input /absolute/guitar.wav \
  --output /tmp/guitar-analysis
uv run --locked resonance align --input /absolute/guitar.wav \
  --score /absolute/reference.json --output /tmp/guitar-alignment
```

Inputs must be 44.1 or 48 kHz mono/stereo audio. Stereo file analysis chooses one
energetic channel from the first second and keeps it for the recording, avoiding
antiphase cancellation. Unsupported rates require explicit resampling rather
than relabeling sample positions. Silence produces no notes; clipping, very
short recordings and uncertain frames produce diagnostics.

Reports preview the first 30 seconds of longer recordings. The note table, JSON
and MIDI cover the full recording, and the playback panel identifies the preview
scope. A score uses versioned JSON, unique note IDs, integer MIDI pitches,
onset/duration in seconds or beats and an explicit tempo; see
[the reference format](examples/reference.json).

The report verifies that its plotted samples match its embedded WAV. Provenance
records the full source-file hash separately from the encoded playback hash,
sample count and full/prefix scope. Keep input files unchanged throughout a run.

For Python callers:

```python
from pathlib import Path
from pp_resonance import analyze_chunks
from pp_resonance.audio_io.pcm import blocks

spec, chunks = blocks(Path("guitar.wav"))
report = analyze_chunks(chunks, spec.sample_rate)
for note in report.notes:
    print(note.midi, note.start / spec.sample_rate, note.cents, note.confidence)
```

The array API `analyze(samples, rate)` accepts a mono vector or stereo
`(samples, 2)` matrix. Chunked analysis keeps the sample buffer bounded, but
retains trajectories and events for offline decoding. Memory therefore grows
with recording duration; this is not an indefinite streaming service.

## Scope and verification

The baseline pitch range is E2–E6. Confidence measures periodicity evidence and is
not a probability of musical correctness. Bends and vibrato remain visible as
pitch spread; an intonation summary does not judge artistic intention. Polyphony,
extreme noise and accuracy across unfamiliar guitars/styles are outside the
validated synthetic guarantees.

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md): algorithms, timing and memory tradeoffs.
- [Numerical methodology](docs/METHODOLOGY.md): pitch/attack semantics, abstention, fixed evaluation denominators and independent oracles.
- [Operations](docs/OPERATIONS.md): commands, input budgets, diagnostics, cleanup and MIDI rules.
- [Fixture contracts](docs/FIXTURES.md), [acceptance map](docs/ACCEPTANCE.md) and [verification history](docs/VERIFICATION.md): reproducible expectations and results.
- [Benchmarks](docs/BENCHMARKS.md), [case study](docs/CASE_STUDY.md) and [provenance](docs/THIRD_PARTY.md): measured behavior and limitations.
- [Core review](docs/CORE_REVIEW.md): reproduced algorithmic defects, rolling-row alignment and bounded baseline comparisons.
