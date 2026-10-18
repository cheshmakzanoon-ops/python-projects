# Resonance

Resonance turns an offline monophonic guitar recording into pitch, onset, note and reference-alignment evidence. Its original NumPy/Python core implements fixed-window YIN, adaptive spectral-flux onsets, confidence-aware temporal decoding and monotone edit alignment. Listen to the actual generated audio beside its waveform, spectrogram, cents offsets and uncertainty in a self-contained HTML report.

```sh
uv sync --locked --python 3.13.16
uv run --locked python -m pp_resonance.cli demo --output /tmp/resonance-demo --seed 1729
# Open /tmp/resonance-demo/analysis.html
uv run --locked python -m pp_resonance.cli benchmark --profile ci --output /tmp/resonance-ci --seed 1729
uv run --locked python -m pp_resonance.cli clean-demo --output /tmp/resonance-demo
```

Use absolute output paths. Nonempty directories require a Resonance ownership marker; cleanup preserves unrelated files. Shell examples use Linux/macOS paths; supply an absolute Windows path on Windows. Linux is the measured platform; Python 3.14.8 is the default; Python 3.13.16 is also a required, verified compatibility target.

```python
import soundfile as sf
from pp_resonance import analyze

samples, rate = sf.read("guitar.wav", dtype="float64")
report = analyze(samples, rate)
for note in report.notes:
    print(note.midi, note.start / rate, note.cents, note.confidence)
```

For bounded input buffers, `audio_io.pcm.blocks` and `analyze_chunks` stream PCM without retaining the recording. Output trajectory/event records grow with duration. Only 44.1/48 kHz mono/stereo files are supported. Stereo chooses one energetic channel rather than summing antiphase signals. Silence produces no notes. Unsupported rates produce an explicit error: try a 22.05-kHz file with `analyze --input FILE --output ABS`.

Other commands: `synthesize`, `analyze --input FILE [--score SCORE]`, `align --input FILE --score SCORE`, `compare` (fixed full pitch grid), and `export --input ANALYSIS_JSON`. All require `--output ABS`. Scores are versioned JSON with explicit seconds/beats and tempo; see [the score example](examples/reference.json).

The clean synthetic pitch grid and isolated plucks are reproducible acceptance fixtures, not evidence of universal real-guitar performance. Polyphony, extreme noise and artistic intention remain outside the inference guarantee. Bends/vibrato appear as median cents and within-event pitch spread; low-confidence frames never become definitive criticism.

Read [architecture](docs/ARCHITECTURE.md), [numerical contracts](docs/FIXTURES.md), [acceptance](docs/ACCEPTANCE.md), [benchmarks](docs/BENCHMARKS.md), [operations](docs/OPERATIONS.md), [case study](docs/CASE_STUDY.md), and [provenance](docs/THIRD_PARTY.md).
