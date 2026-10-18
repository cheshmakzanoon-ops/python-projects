# A10 Resonance status

State: verifying; implementation and local matrix are ready for stable coordinator handoff. Source/docs frozen. Only coordinator-owned committed-snapshot verification and the exclusive standard workload remain.

Development evidence source: Git HEAD `3f2c220333fce195c858fa1f08df21676dd51ff1`, dirty=true (implementation not yet integrated when measured); source-content SHA-256 `ff3adaf492028e4a921d049a5c9f8aa3cdc3af260cdea059883c2fd114b572d1`. See artifacts/development-ci-benchmark.json for exact source input list, root/lock hashes, versions, environment and thread settings. Generated artifacts and this status file are excluded from the content digest.

## Completed locally

* RE-01: frozen MIDI40–88 ×44.1/48k grid, all 6,272 predetermined eligible frames voiced and within10c; conditional median0.0290c/p950.3812c. Explicit regression counts missing/unvoiced/NaN/Inf/zero/out-of-tolerance as failures and reports all-abstention conditional error as null.
* RE-02: silence/empty/short/clipped/stereo antiphase/unsupported rates/nonfinite inputs and safe file boundaries.
* RE-03: Hypothesis chunk/padding/flush oracle, four randomized full-phrase chunkings with identical frames, pitch, onset and note outputs; no timestamps shifted or duplicate flush frames.
* RE-04: direct fixed-window squared-difference oracle; NumPy STFT/inverse versus independent SciPy reference at fixed1e-10/1e-11 tolerances.
* RE-05: exact six clean pitches/onsets, zero extra/missed notes and no release/silence onsets; <=60ms onset/80ms offset gates. Additional adjacent same-pitch reattack regression.
* RE-06: exact fixed insertion/deletion mapping, timing perturbation/uncertainty cases, continuous bend/vibrato retained as one event with spread.
* RE-07: JSON/MIDI timing agreement, independent standard-MIDI byte checker plus mido round-trip; custom tempo and quantized-subtick rejection before writing.
* RE-08: playable HTML for demo and arbitrary input, actual encoded audio/waveform/spectrogram/notes/reference/cents/confidence/spread, provenance and safe owned cleanup. Input buffers verified bounded in properties and full60-second CI run. The600-second standard execution is still pending coordinator's exclusive lease.

## Commands and results

Environment: uv0.12.23, CPython3.13.16 and3.14.8 on Linux; OMP/OPENBLAS/MKL thread variables=1; default pin now3.14.8. Both Python versions use the same committed uv.lock resolutions. CPython3.13 remains required.

* `uv run --locked --python 3.13.16 ruff format --check .` / `ruff check .` / `mypy src`: exit0.
* Same quality commands via `UV_PROJECT_ENVIRONMENT=/tmp/resonance-314 uv run --locked --python 3.14.8 ...`: exit0.
* Python3.13 `pytest -q --cov=pp_resonance --cov-branch --cov-report=term-missing --cov-report=json:results/coverage313.json`:25 passed in24.67s;94.01% statements,92.07% branches,93.54% combined; no exclusions. Numerical DSP modules97–100%; benchmark orchestration30% is covered by real CLI execution rather than mocked timing tests.
* Python3.14 `pytest -q`:25 passed in14.26s.
* `uv build`: exit0, wheel and sdist produced.
* Exact locked runtime requirements exported with hashes, installed with `uv pip install --require-hashes` into fresh `/tmp/resonance-wheel313` and `/tmp/resonance-wheel314`; final rebuilt wheel reinstalled with no dependencies. Both final `python -m pp_resonance.cli demo --output /tmp/resonance-reviewedwheelVERSION --seed 1729` run from `/tmp`: exit0, six notes/MIDI checked, playable reports written outside checkout.
* Final Python3.14 `python -m pp_resonance.cli benchmark --profile ci --output /workspace/resonance-finalci --seed 1729`: exit0, one warmup/five measured60s challenge runs, median2.96335s, measured factor0.049389; peak RSS84,578,304 bytes, sample buffer9,984<=10,239. Source and root hashes unchanged during run. Challenge separately reports78 matched notes/0 extras/0 misses,79 onset events/1 extra,3 bend-related >50c alignment deviations; no false voiced silence frames. Synthetic metrics do not establish real-recording accuracy.

## Independent review corrections

A05 independently found and supplied three reproducible defects: contiguous same-pitch attacks merged despite two onsets; a one-sample interval rounded to zero ticks and serialized invalid MIDI; the byte checker rejected valid nondefault tempos. All reproduced, fixed and covered by meaningful regressions plus the full interpreter matrix. Earlier original flux implementation also detected releases; the rising-energy gate and fixture regression exclude that failure.

## Remaining work and restart

Coordinator: commit stable A10 source, set manifest default Python3.14.8 (both3.13/3.14 required), clone that exact commit immutably with Git metadata, rerun required gates/clean wheel and standard600s benchmark serially. No worker standard run has been started. No credentials/services/shared dependencies are missing. There are no active source edits, failing commands or unresolved local code blockers.

Demo: `uv run --locked python -m pp_resonance.cli demo --output /tmp/resonance-demo --seed 1729`; no service restart needed. Standard: same CLI `benchmark --profile standard --output ABS --seed 1729`. Retained output records and DP state grow with duration/event counts; only sample input buffers are bounded. Real guitar, polyphony, extreme noise and hard real-time behavior remain outside validated synthetic guarantees.
