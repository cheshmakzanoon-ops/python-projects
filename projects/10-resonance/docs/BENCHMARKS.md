# Benchmarks

The accepted standard run processed a 600-second synthetic recording on CPython 3.14.8 from clean committed source `59443e2bcdfc6a1dd81f8334c108474eef2d3030`. The [raw benchmark](../../../docs/evidence/final/standard/resonance-3.14.8-benchmark-benchmark.json) records every metric and input; the [verification wrapper](../../../docs/evidence/final/standard/resonance-3.14.8.json) records the successful demo/standard commands and unchanged source after execution. This is measured offline processing on the recorded Linux/Xeon environment, not a hard real-time guarantee or a cross-machine speed claim.

The workload uses seed 1729, 48,000 Hz audio, 2,048-sample frames, 256-sample hops, 8,192-sample input blocks, one process, and OMP/OpenBLAS/MKL thread counts of one. It contains harmonics, rests, noise standard deviation 0.0005, annotated onset perturbations of -25/0/+25 ms, 20-cent vibrato and 100-cent bend parameters. A four-second kernel warmup with the first four tones precedes five full 600-second measurements. Chunk synthesis, framing, pitch, onset and note decoding are timed; alignment, subsequent numerical evaluation, disk output and HTML rendering are outside those processing times.

| Measurement | Accepted result |
| --- | --- |
| Five processing times, seconds | 24.818886651, 25.890807995, 25.151596931, 25.449761711, 24.508211711 |
| Median / interpolated p95, seconds | 25.151596931 / 25.802598738 |
| Processing/audio-duration ratio | 0.0419193282 |
| Audio seconds processed per second | 23.855344122 |
| Recorded peak process RSS | 151,752,704 bytes |
| Peak retained input buffer | 9,984 samples; bound 10,239 |
| Fixed RE-01 grid | 6,272/6,272 eligible frames voiced and within 10 cents |
| Fixed-grid median / p95 absolute error | 0.0290458194 / 0.3812231044 cents |
| Challenge eligible voiced frames | 40,417; zero voiced misses; all within 10 cents of analytic instantaneous frequency |
| Challenge silent frames | 43,306; zero false voiced frames |
| Challenge pitch median / p95 absolute error | 0.1411067400 / 2.4102081200 cents |
| Challenge mean voiced confidence | 0.9992231586 |
| Challenge note events | 798 truth, 798 detected/matched, zero misses or extras |
| Challenge onset events | 798 truth, 800 detected, zero misses and two extras |
| Matched onset mean / maximum absolute error | 0.0051002506 / 0.0086666667 seconds |
| Challenge note pitch mean absolute error | 0.0225563910 semitones against nominal MIDI pitches |
| Alignment | 798 matches, zero gaps, cost 31.07; 18 matched summaries more than 50 cents from nominal pitch |
| Alignment processing time | 3.558448477 seconds |

All four recorded correctness checks passed: the fixed RE-01 threshold, bounded input buffer, all samples processed, and unchanged source/root hashes. The two extra onset detections and 18 nominal-pitch alignment deviations remain reported challenge errors; a passed benchmark does not mean zero transcription errors. The fixed clean-pluck and insertion/deletion gates retain their separately declared tolerances in [FIXTURES.md](FIXTURES.md).

The timing perturbations are already part of the performed audio **and** its benchmark reference. `synthesis/tones.py::challenge` changes each `Tone.onset`; `benchmark.py` constructs `ReferenceNote.start` from that same perturbed onset, while onset/note metrics compare detections with it. Consequently, the roughly 5.10 ms onset error measures detector accuracy relative to the generated attacks. It does not measure recovery of a player's +/-25 ms deviation from an unperturbed score, and the standard alignment has no intentional inserted or omitted notes. RE-06 tests that different correspondence problem independently.

Pitch metrics also have distinct reference meanings. Challenge trajectory error uses the analytic instantaneous frequency including bend/vibrato phase modulation. Note-event pitch and alignment compare a median event summary with the tone's nominal MIDI pitch; `alignment_wrong_pitch_count` counts absolute summary offsets above 50 cents. Intentional bends can therefore contribute to nominal-pitch deviations despite accurate instantaneous tracking. The aggregate result does not identify the cause of each of the 18 deviations, and it does not establish subjective musical correctness.

Only input sample buffers have the stated fixed bound. Trajectory/event records grow with duration, and dynamic-programming alignment grows with reference and detected event counts. RSS is the recorded process high-water value after timed analysis, alignment and fixed-grid evaluation, including imported libraries and retained outputs; it is not a bound on every later reporting allocation. The 600-second run establishes the declared long-recording execution gate, not constant total memory for arbitrary durations.

The wrapper hashes executable project inputs separately from the raw benchmark's broader source scope, which also includes the then-existing project documentation; each file lists its exact inputs. Both identify the tested commit and the same lockfile. The [Python 3.13 wrapper](../../../docs/evidence/final/python313/resonance-3.13.16.json) and [Python 3.14 wrapper](../../../docs/evidence/final/python314/resonance-3.14.8.json) record clean compatibility checks, demos and CI workloads on the accepted executable project content. Earlier [dirty development measurements](../artifacts/development-ci-benchmark.json) remain historical captures. No licensed real-guitar corpus was evaluated; synthetic results do not establish real-recording or polyphonic accuracy.
