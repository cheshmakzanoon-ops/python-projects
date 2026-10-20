# Operations

Install the project independently with `uv sync --locked --python 3.14.8`. Python 3.13.16 remains a tested compatibility target; use an explicit interpreter and a separate environment when switching versions. No GPU, microphone, network service, API key or external recording is required after dependencies install. Never commit local audio that lacks redistribution permission.

For reproducibility set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`; a writable `MPLCONFIGDIR` avoids slow temporary font cache creation in read-only home environments. Run Ruff format/check, `mypy src`, `pytest`, and `uv build`. The clean-wheel verification installs the distribution into a fresh environment and runs its demo outside the checkout.

`demo --output ABS --seed 1729` writes audio.wav, analysis.json/html/png, reference.json and transcription.mid plus an ownership marker. These can be opened without an HTTP server. Playback is the actual encoded PCM, not a synthesized reconstruction of estimated notes. JSON version 1 stores integer sample times, configuration, all unvoiced frames and source/audio hashes. Save the complete output directory to archive a run; there is no mutable service/database to restore.

`analyze --input FILE --output ABS [--score SCORE]` reads bounded SoundFile blocks, rejects unsupported rates/channels, and writes analysis.json, MIDI and a playable HTML report. Playback/figures use a bounded first-30-second clip; JSON/MIDI retain the whole recording. `align` uses the same audio analysis plus the reference; `export` rebuilds MIDI from analysis JSON. `compare` evaluates the frozen full pitch grid. `synthesize` creates the clean six-pluck phrase.

Reference scores are UTF-8 JSON, at most 4,000,000 bytes and 10,000 notes. Analysis
JSON supplied to `export` is limited to 64,000,000 bytes. JSON nesting is limited
to 64 levels; nonfinite numbers, nonregular files and malformed record shapes are
rejected. Scores require numeric tempo/onset/duration values, integer MIDI pitches
and unique nonempty IDs of at most 200 characters. Boolean values are not numbers
in these contracts.

Alignment retains one byte per traceback cell and two rolling cost rows. The
default budget is 4,000,000 cells (including the leading row/column), about 4 MB
for traceback plus Python cost rows and result records, checked before allocation.
The running time is still quadratic. Split a long reference into phrases if that budget is exceeded. Python
callers may opt into a larger `align(..., max_cells=N)` budget after accounting for
both memory and quadratic running time. Empty-reference and empty-detection cases
remain supported. Frame size and hop must be integers; supported analysis frame
sizes are 1,024–65,536 samples, with hop in `[1, size]`. Thresholds must be finite.

`benchmark --profile ci|standard --output ABS --seed 1729` processes 60s/600s of generated audio with harmonics, rests, bends, vibrato, noise and timing perturbations, one warmup and five timed repetitions. Standard runs require exclusive machine access. Timing excludes plot generation and file output. Peak process RSS is a high-water mark, not a per-allocation delta; unsupported OS memory measurement is null. Retained output records are intentional and not part of the bounded input buffer guarantee.

`clean-demo --output ABS` validates ownership and deletes only its known generated names and marker. It refuses symlinked output files; it preserves arbitrary additional user files. Never recursively delete an arbitrary selected directory. Concurrent writers to the same output directory are unsupported: use isolated paths per run.

Diagnostics: clipping means full-scale input may distort periodicity; short files cannot establish notes; aperiodic/uncertain frames remain in the trajectory. Low confidence is not a musical error. If a stereo instrument disappears in one channel, inspect both channels or convert explicitly before analysis. Resample unsupported rates with an explicitly configured external converter; never relabel a file's sample rate.

MIDI timing policy: 480 ticks/beat, explicit default 120 BPM. Any positive sample interval that rounds to zero MIDI ticks is rejected before output is written. The Python export API accepts a different positive 24-bit microseconds-per-beat tempo; the independent checker validates it without assuming 120 BPM.

## Python API ownership and evaluation

`analyze_chunks` consumes each feed completely, including its final empty flush.
For direct framer use, `feed` immediately copies input. Exhaust a `FrameBatch`,
or call its `close()` before feeding again. Closing does not discard pending
samples. If a final batch was interrupted, resume it with
`framer.feed(np.empty(0), final=True)`; appending new samples after beginning the
flush raises an error. Reusing a caller's array after feed is safe, and each
returned frame owns an independent copy. To retain the chunk-plus-overlap memory
bound, drain batches before appending input; repeated early closes can retain a
larger backlog. A framer is not thread safe.

Challenge trajectory evaluation now requires independent recording length:

```python
from pp_resonance.metrics.evaluate import trajectory_metrics

metrics = trajectory_metrics(
    report.pitches,
    tones,
    report.sample_rate,
    report.config.frame.size,
    sample_count=report.sample_count,
    hop=report.config.frame.hop,
)
```

Dropping output frames no longer improves coverage by removing them from the
denominator. Duplicate/off-grid timestamps are rejected. Consumers must accept
JSON null for conditional errors when nothing was measured; miss counts and
coverage remain numeric. See [METHODOLOGY.md](METHODOLOGY.md) before comparing
pitch, note-summary and attack measures.

Keep source recordings unchanged for the whole analysis, hash and preview read.
`provenance.audio_sha256` identifies the source bytes; `provenance.playback`
identifies the exact encoded WAV embedded in HTML, with its rate/count and
`full` or `prefix` scope. Rendering rejects a supplied plot array that differs
from those decoded bytes. Preserve JSON, HTML, WAV and MIDI together. If playback
appears unrelated to the figure, verify the playback digest and regenerate the
whole output directory from an immutable input instead of replacing one file.

## Focused core workload

Run the bounded review exercise independently of the 60/600-second profiles:

```sh
uv run --locked python benchmarks/core_review.py --output /tmp/resonance-core.json
```

It measures 100/300/600-reference-note alignment problems with three repetitions
and one 12-second authored phrase at alternating amplitudes. It records source,
workload and dataset hashes, mapping hashes, input-derived pitch coverage and
semantic witnesses. Set numerical threads to one as above. Compare only reports
with matching workload/dataset hashes and read the shared-host timing limits.
The exercise does not replace the clean pitch-grid gate or a real-recording
corpus evaluation. Historical baseline reproduction and exact measurements are
in [CORE_REVIEW.md](CORE_REVIEW.md).
