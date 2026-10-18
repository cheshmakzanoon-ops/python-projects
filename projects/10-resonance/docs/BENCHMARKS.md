# Benchmarks

The fixed RE-01 pitch grid is frozen in FIXTURES.md. Initial development evaluation: 6,272 eligible frames, all 6,272 voiced and within 10 cents, conditional median absolute error 0.0290 cents, p95 0.3812 cents. This is a synthetic held-to-contract fixture; no real-recording accuracy claim follows.

CI generates a 60-second challenge; standard generates 600 seconds. Both include harmonics, Gaussian-like counter-indexed noise, rests, +/-25ms annotated timing perturbations, 20-cent vibrato and 100-cent bends. Generator phase determines challenge ground truth. Clean-grid and clean-pluck acceptance results remain separate from challenge metrics.

The runner records exact source/root/lock digests and Git dirty state, Python/OS/CPU/memory limit, seed/dataset hash, input parameters and thread settings. It uses one kernel warmup, five measured repetitions, median/p95 processing times, measured real-time factor (processing/audio duration), throughput, process high-water RSS and peak sample buffer. Metrics include fixed-grid denominator/recall/error, challenge pitch/voicing/silence errors/confidence, onset/note quality and alignment costs/gaps/wrong-pitch counts. Timing excludes synthesis file writing and HTML plots, but includes chunk synthesis and DSP. Peak RSS includes imported libraries and retained output records.

Run commands in README and OPERATIONS. CI/standard output goes outside source to avoid evidence self-reference. Final standard measurements are pending coordinator's serial resource lease on a committed immutable export. Development timing is a baseline, not a cross-machine speed claim.
