# Acceptance mapping

Frozen denominator/tolerances and exact score correspondence are in [FIXTURES.md](FIXTURES.md). Tests run the installed src-layout package through public interfaces; generator parameters are independent ground truth.

| Gate | Evidence |
|---|---|
| RE-01 | `tests/acceptance/test_acceptance.py::test_RE01_fixed_full_denominator`: all 49 semitones × both rates, 6,272 predetermined frames; failed/unvoiced frames remain failures. `compare` and benchmark JSON reproduce statistics. |
| RE-02 | `tests/unit/test_audio.py`: silence, empty/short, full-scale clipping, antiphase stereo, rates, nonfinite samples and fixed streaming channel selection. |
| RE-03 | `tests/property/test_framing.py`: Hypothesis chunk sequences versus independently padded arrays; four random full phrase chunkings produce identical pitch/onset/note records and timestamps; flush exactly once. |
| RE-04 | `tests/unit/test_numerics.py`: independent direct-sum YIN and SciPy STFT/inverse reference, 1e-10/1e-11 tolerances. |
| RE-05 | `test_RE05_clean_events_no_silent_inventions`: six exact-pitch notes/onsets, zero extra/missing, onset <=60ms, offset <=80ms; note-off regression; adjacent same-pitch reattack regression with no silent gap. |
| RE-06 | `test_RE06_expected_insert_delete_mapping`: exact predetermined match/unmatched sets, timing perturbations and uncertainty gating; separate bend/vibrato spread test. |
| RE-07 | `tests/integration/test_outputs.py`: actual generated MIDI checked through independent byte parser and mido readback, explicit tempo, note-offs and half-tick JSON timing agreement; sub-tick rejection preserves an existing file; custom-tempo round-trip. |
| RE-08 | same integration test drives playable HTML/encoded audio/actual plot/provenance and safe cleanup; bounded-buffer property plus accepted [600-second standard raw evidence](../../../docs/evidence/final/standard/resonance-3.14.8-benchmark-benchmark.json) closes long-recording execution: 112,500 frames, peak input buffer 9,984 <= 10,239 samples. |

Required reproducible checks: `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, `uv run --locked mypy src`, `uv run --locked pytest`, `uv build`; both supported interpreters and clean wheel runs. Accepted clean compatibility evidence is available for [Python 3.13.16](../../../docs/evidence/final/python313/resonance-3.13.16.json) and [Python 3.14.8](../../../docs/evidence/final/python314/resonance-3.14.8.json), each with 25 passing tests, format/lint/types, build, clean-wheel demo and CI workload. The [independent review](../../../docs/evidence/INDEPENDENT_REVIEW.md) includes direct numerical and MIDI checks and the repeated-pitch/subtick/tempo corrections.

RE-01–RE-08 are closed for their declared synthetic fixtures and platform. The final standard [wrapper](../../../docs/evidence/final/standard/resonance-3.14.8.json) and [raw measurements](../../../docs/evidence/final/standard/resonance-3.14.8-benchmark-benchmark.json) identify clean tested commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030` and unchanged executable source. All four benchmark correctness checks passed. Challenge metrics still include two extra onset events and 18 aligned summaries more than 50 cents from nominal pitch; these do not replace or relax the fixed clean gates. See [BENCHMARKS.md](BENCHMARKS.md) for timing/reference interpretation and memory limits. Historical dirty development captures remain separate; no real-recording, polyphonic or hard real-time guarantee is implied.
