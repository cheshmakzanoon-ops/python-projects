# Operations

Install the project independently with `uv sync --locked --python 3.13.16`. Python 3.14.8 is the default; explicitly selecting 3.13.16 retains the supported baseline. No GPU, microphone, network service, API key or external recording is required after dependencies install. Never commit local audio that lacks redistribution permission.

For reproducibility set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`; a writable `MPLCONFIGDIR` avoids slow temporary font cache creation in read-only home environments. Run Ruff format/check, `mypy src`, `pytest`, and `uv build`. The clean-wheel verification installs the distribution into a fresh environment and runs its demo outside the checkout.

`demo --output ABS --seed 1729` writes audio.wav, analysis.json/html/png, reference.json and transcription.mid plus an ownership marker. These can be opened without an HTTP server. Playback is the actual encoded PCM, not a synthesized reconstruction of estimated notes. JSON version 1 stores integer sample times, configuration, all unvoiced frames and source/audio hashes. Save the complete output directory to archive a run; there is no mutable service/database to restore.

`analyze --input FILE --output ABS [--score SCORE]` reads bounded SoundFile blocks, rejects unsupported rates/channels, and writes analysis.json, MIDI and a playable HTML report. Playback/figures use a bounded first-30-second clip; JSON/MIDI retain the whole recording. `align` uses the same audio analysis plus the reference; `export` rebuilds MIDI from analysis JSON. `compare` evaluates the frozen full pitch grid. `synthesize` creates the clean six-pluck phrase.

`benchmark --profile ci|standard --output ABS --seed 1729` processes 60s/600s of generated audio with harmonics, rests, bends, vibrato, noise and timing perturbations, one warmup and five timed repetitions. Standard runs require the coordinator's exclusive resource lease. Timing excludes plot generation and file output. Peak process RSS is a high-water mark, not a per-allocation delta; unsupported OS memory measurement is null. Retained output records are intentional and not part of the bounded input buffer guarantee.

`clean-demo --output ABS` validates ownership and deletes only its known generated names and marker. It refuses symlinked output files; it preserves arbitrary additional user files. Never recursively delete an arbitrary selected directory. Concurrent writers to the same output directory are unsupported: use isolated paths per run.

Diagnostics: clipping means full-scale input may distort periodicity; short files cannot establish notes; aperiodic/uncertain frames remain in the trajectory. Low confidence is not a musical error. If a stereo instrument disappears in one channel, inspect both channels or convert explicitly before analysis. Resample unsupported rates with an explicitly configured external converter; never relabel a file's sample rate.

MIDI timing policy: 480 ticks/beat, explicit default 120 BPM. Any positive sample interval that rounds to zero MIDI ticks is rejected before output is written. The Python export API accepts a different positive 24-bit microseconds-per-beat tempo; the independent checker validates it without assuming 120 BPM.
