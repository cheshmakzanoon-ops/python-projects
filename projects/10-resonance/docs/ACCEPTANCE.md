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
| RE-08 | same integration test drives playable HTML/encoded audio/actual plot/provenance and safe cleanup; bounded-buffer property plus standard 600-second benchmark closes long-recording execution. |

Required reproducible checks: `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, `uv run --locked mypy src`, `uv run --locked pytest`, `uv build`; both supported interpreters and clean wheel runs. Final immutable evidence is coordinator-owned. Local development evidence is not a claim of final committed-source verification.
