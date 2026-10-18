# A10 Resonance status

State: complete for the declared local acceptance scope. RE-01–RE-08, both required interpreter checks, independent numerical/MIDI review and the 600-second standard workload have accepted evidence. No project implementation blocker remains. Repository-level commit/push and remote CI reporting remain coordinator-owned.

The accepted standard [raw report](../../../docs/evidence/final/standard/resonance-3.14.8-benchmark-benchmark.json) and [wrapper](../../../docs/evidence/final/standard/resonance-3.14.8.json) tested clean commit `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. The wrapper confirms unchanged executable source after execution and source-content hash `b8b1d5d2662ad6d12b76b83da99b08ed1e271bcc471e68b8c300e5f9439497d6`. The raw report's broader scope, including then-existing documentation, has hash `ff3adaf492028e4a921d049a5c9f8aa3cdc3af260cdea059883c2fd114b572d1`. Each lists its inputs; both record lock hash `8ac205930d14ebd160772d9950380e6e966aa61e740a0f3cd169c195f15cbefc`.

## Accepted gates

* RE-01: all 6,272 predetermined MIDI 40–88 frames at 44.1/48 kHz were voiced and within 10 cents. Median absolute error was 0.0290458194 cents; p95 was 0.3812231044 cents. Missing, unvoiced, nonfinite, nonpositive and out-of-tolerance outputs count as failures; all-abstention conditional error is null.
* RE-02: silence, empty/short recordings, clipping, antiphase stereo, unsupported rates, nonfinite samples and file boundaries are covered.
* RE-03: Hypothesis framing/flush oracles and randomized full-phrase chunkings preserve exact frame positions and pitch/onset/note outputs.
* RE-04: direct squared-difference and independent SciPy STFT/inverse checks meet the fixed 1e-10/1e-11 tolerances.
* RE-05: six fixed clean pitches/onsets meet the predeclared onset/offset tolerances with no missing or extra notes or release/silence onsets. Adjacent same-pitch reattacks have a separate regression.
* RE-06: the fixed insertion/deletion mapping, timing perturbation, uncertainty and continuous bend/vibrato cases pass.
* RE-07: JSON/MIDI timing, independent byte parsing, mido round-trip, custom tempo and rejection of collapsed subtick intervals before writing pass.
* RE-08: playable HTML/audio/plots/notes/reference/cents/confidence/provenance and safe cleanup pass; the accepted 600-second standard run processes 112,500 frames with peak retained sample buffer 9,984 <= 10,239.

## Compatibility, review and measurements

The clean [Python 3.13.16 wrapper](../../../docs/evidence/final/python313/resonance-3.13.16.json) and [Python 3.14.8 wrapper](../../../docs/evidence/final/python314/resonance-3.14.8.json) record successful format/lint, strict mypy, 25 tests each, wheel/sdist, clean-wheel demo, seeded demo and CI benchmark at commit `7114e39c7e9e8af177e84fe8cd990fe5a09bde63`. Their executable project hash matches the standard wrapper above. Python 3.14.8 is the default; 3.13.16 remains required. The [independent review record](../../../docs/evidence/INDEPENDENT_REVIEW.md) confirms numerical/export checks and the corrected same-pitch reattack, zero-tick ordering and nondefault-tempo reproductions.

Standard parameters: seed 1729; 600 seconds at 48 kHz; frame/hop/block 2,048/256/8,192 samples; one process; OMP/OpenBLAS/MKL threads one; one four-second kernel warmup and five full measurements. Processing times were 24.818886651, 25.890807995, 25.151596931, 25.449761711 and 24.508211711 seconds. Median was 25.151596931 seconds, interpolated p95 25.802598738 seconds, measured processing/audio-duration ratio 0.0419193282, and throughput 23.855344122 audio seconds per second. Recorded peak RSS was 151,752,704 bytes. All four correctness checks passed.

Challenge results remain visible: 798 truth/detected/matched note events with no note misses/extras; 800 detected onset events, including two extras; 18 aligned summaries over 50 cents from nominal pitch; alignment cost 31.07. Matched onset mean absolute error was 5.1002506 ms. The 40,417 eligible voiced frames had no misses and all tracked analytic instantaneous frequency within 10 cents; 43,306 fully silent frames had no false voicing. These results do not promise zero transcription errors. Onset perturbations are shared by generated audio and its reference, so attack error measures detection relative to performed synthetic attacks. Nominal note-summary deviations and instantaneous bend/vibrato tracking use different pitch references; see [BENCHMARKS.md](BENCHMARKS.md).

## Historical captures and limits

[Development CI evidence](../artifacts/development-ci-benchmark.json), [verification](../artifacts/development-verification.json), and [sample outputs](../artifacts/sample-manifest.json) retain their original dirty-source identifiers; they have not been relabeled as final measurements. Historical development coverage was 94.01% statements and 92.07% branches, without exclusions.

Only sample input buffers have a fixed bound. Retained trajectories/events and alignment state grow with duration/event counts. RSS is the recorded high-water sample after the timed processing, alignment and fixed-grid evaluation, not a constant bound on all later reporting allocations. Real-guitar corpus accuracy, polyphony, extreme-noise behavior and hard real-time operation remain outside the validated synthetic guarantees.

Documentation handoff: only CASE_STUDY.md, BENCHMARKS.md, AGENT_STATUS.md and ACCEPTANCE.md were updated to describe accepted evidence. Source, tests, dependencies and historical captures are unchanged. No new tests or benchmarks were run for this documentation update; all writes are paused for coordinator review.

## 2026-10-18 correctness review

The subsequent working-tree review added 26 boundary regression cases. Cleanup now rejects symlink ownership markers and checks every owned output for symlinks before deleting any files. Analyze/align/export refuse to overwrite inputs, including hard-linked audio and reference scores sharing an output filename; corrupt audio produces a CLI diagnostic instead of an uncaught SoundFile exception. Cents calculations reject nonfinite inputs and use separate logarithms to avoid ratio overflow/underflow; trajectory metrics count invalid estimates as misses. MIDI export rounds half ticks exactly, rejects deltas exceeding the standard 28-bit field before writing, and its independent checker rejects malformed end markers, invalid 7-bit data and zero-length notes. Reference durations must remain finite and positive after sample quantization.

Verification on the modified working tree: full `pytest -q -W error::ResourceWarning` passed **51 tests** on CPython 3.14.8 and **51 tests** on CPython 3.13.16. Ruff format/check and strict `mypy src` passed (28 source files). `uv build --out-dir /tmp/resonance-review-dist` produced an sdist and wheel. No dependency declarations or lockfiles changed. No costly benchmark was rerun; the performance evidence above remains evidence for its recorded source. Input/output aliasing now requires a separate output directory. The validated scope remains offline monophonic synthetic audio, with retained trajectories/events growing with duration.
