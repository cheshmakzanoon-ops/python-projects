# Numerical model and evaluation

Resonance analyzes a single predominant musical pitch in mono PCM at 44.1 or
48 kHz. Validation uses authored signals with explicit event metadata and
analytic phase. It does not establish accuracy on recorded guitar performances,
polyphonic mixtures, arbitrary effects chains or extreme noise.

## Pitch model and abstention

For a frame `x` of length `N`, maximum lag `M`, and fixed width `W=N-M`, the
difference function is:

```text
d(tau) = sum((x[j] - x[j + tau])**2 for j in range(W))
cmnd(0) = 1
cmnd(tau) = tau * d(tau) / sum(d(k) for k in range(1, tau + 1))
```

Exactly zero cumulative energy leaves the normalized value at one. Every
positive denominator is divided, with no absolute epsilon in energy units.
Multiplying a waveform by a nonzero scalar multiplies numerator and denominator
by the same squared scalar. Above the configured silence threshold, the
dimensionless decision should therefore be invariant within floating-point
precision. The default silence threshold still intentionally rejects quiet PCM.
Values near floating-point underflow/overflow are outside an ordinary audio
representation; there is no claim of scale invariance across underflow.

The implementation subtracts the frame mean, evaluates correlation with an FFT
and forms squared sums with a prefix array. A direct quadratic sum checks lag
indexing independently. Small negative differences from FFT roundoff are clamped
to zero. Detection takes the first sub-threshold trough within the lag range,
descends to its local minimum, and interpolates its position by at most half a
lag. Frequency is sample rate divided by interpolated lag. Confidence is
`1-cmnd` at the discrete trough, clamped to `[0,1]`; it is a periodicity measure,
not a calibrated probability of a correct musical note.

Frames below the silence RMS, without a qualifying trough, or below minimum
confidence have `frequency=None` with an explicit reason. They remain in the
trajectory and in evaluation denominators. No interpolation fills an unvoiced
frame with an invented pitch. The decoder can bridge two missing frames to avoid
turning a brief estimator dropout into a new musical attack.

## Temporal decisions

Spectral flux measures positive changes in windowed magnitude. Its adaptive
threshold uses the larger of an absolute numerical floor, 8% of the local
maximum, and 1.5 times the local median, all within ±8 frames. A three-frame
average of RMS must rise by more than 0.1%; it reduces pitch-period ripple while
rejecting falling-energy releases. Candidate peaks are selected chronologically
and must be separated by at least 100 ms. The first qualifying peak wins within
that interval. This is a declared refractory policy, not a strongest-peak search
or an arbitrarily fine attack detector.

Appending samples beyond the adaptive neighborhood cannot change an established
earlier attack. An appended peak inside that neighborhood can legitimately
change a threshold. Final frames have truncated neighborhoods. An attack at the
very first or last trajectory element has no two-sided local maximum test;
pitch decoding can still establish a note without an onset event.

Note segmentation uses voiced centers, minimum duration, pitch hysteresis and
credible attacks. The same `.5` attack-confidence gate applies to event splitting,
boundary snapping and reattack support. A note's median frequency describes the
whole event. Its cents deviation from nearest MIDI pitch and its percentile
spread describe tuning and variation; neither replaces instantaneous tracking.
Smooth bends can span a semitone without constituting another attack.

## Fixed input denominators

`trajectory_metrics` requires `sample_count`, frame size and hop independently
of the estimator output. It constructs the complete grid `range(0, count, hop)`
and joins estimates by start sample. Duplicate, out-of-grid and inconsistent
center timestamps are rejected. Missing output at an eligible voiced frame is
a miss; deleting output cannot shrink the denominator. The returned expected
frame count and missing-output count also expose omissions in silent intervals.

A frame is pitch-eligible when its center is at least 100 ms after an authored
attack and at least 50 ms before the event ends. These fixed exclusions avoid
crediting mixed attack/release windows as steady-state pitch observations. A
fully silent frame has no overlap between its complete window and any authored
event. Mixed boundary frames contribute to neither category. These conditions
depend on the generator metadata, never on whether the estimator voiced a frame.

For each eligible center, the reference is the derivative of the authored phase:
the nominal frequency multiplied by `1 + vibrato + bend`. The generator uses a
small-modulation approximation proportional to `log(2)/1200`, not an exact
exponential cents ramp. The evaluator uses that same analytic specification;
an independent workload derives it with Python scalar math rather than importing
the evaluator. Numerical tolerance and synthetic-model agreement do not imply
agreement with an independently recorded instrument.

Reported measures have distinct meanings:

| Measure | Denominator and interpretation |
| --- | --- |
| Voicing recall | Valid positive finite estimates / all eligible voiced frames |
| Within 10 cents | Valid estimates within tolerance / all eligible voiced frames |
| Conditional median/p95 error | Errors only where a valid voiced estimate exists |
| Silent false voicing | Valid voiced estimates in fully silent input windows |
| Missing output frames | Absent records on the complete input-derived grid |

Missing, unvoiced, zero, negative and nonfinite frequency estimates fail voiced
coverage. Conditional pitch errors/confidence are `null` when undefined.
Event onset/pitch errors are also `null` when no events match; zero is reserved
for an actual zero measured error. Miss and extra counts always accompany event
errors. For note/onset summaries, the evaluator uses ordered nearest-time
matching within 150 ms, independently of production edit alignment. This greedy
event summary is appropriate to the spaced authored phrases; dense ambiguous
attacks need an independently specified matching protocol before making accuracy
claims.

The separate clean acceptance grid has 6,272 predeclared frames across MIDI
40–88 at both supported rates. It uses its own fixed expected-start dictionary;
abstention and omitted frames count as failures. Passing that grid does not turn
the challenge fixture into a real-recording accuracy assessment.

## Alignment objective and independent verification

For reference `r` and detection `n`, the match cost is:

```text
1.5 * abs(r.midi - n.midi)
+ min(2, abs(r.start * tempo_scale - n.start) / sample_rate)
+ (3 if n.confidence < 0.8 else 0)
```

Each unmatched note costs 1.2. Duration and within-semitone cents are reported but
do not affect the objective. This choice permits explicit gaps instead of forced
wrong-pitch or uncertain matches. Uniform `tempo_scale` acts about sample zero;
callers must explicitly establish an appropriate phrase origin. Automatic tempo
estimation, local warping and offset search are unsupported.

Tests enumerate every monotone edit path for 40 small seeded problems, score
each path directly and compare its minimum with the returned alignment. Separate
cases specify diagonal-first exact ties, deletion/insertion ordering, empty
inputs and explicit tempo. Larger deterministic workloads assert complete
reference/detection consumption and compare mapping digests across snapshots.
This separates correctness evidence from a benchmark of the recurrence itself.

## MIDI and playable evidence

Integer samples are converted to 480 ticks per beat using exact rational
rounding and an explicit tempo. Independent tests parse with mido, accumulate
absolute event ticks and bound the reconstructed rational seconds within half a
tick at two sample rates and four tempos. A separate byte checker verifies the
restricted generated MIDI format and note lifecycle. Collapsed sub-tick notes
are refused; coincident note-off precedes note-on.

Playback is encoded PCM, never a reconstruction from estimated notes. Before
rendering, SoundFile decodes the captured WAV and its exact samples/rate must
match the plotted clip. HTML and JSON share a playback digest and scope. The
full source-file hash identifies the recording supplied to analysis; the
playback hash identifies the particular re-encoded full clip or prefix embedded
in the report. Keep inputs immutable during a run. Neither hash independently
proves the correctness of musical estimates.

## Bounded review results

[CORE_REVIEW.md](CORE_REVIEW.md) records concrete baseline failures, the exact
workload and raw snapshot comparisons. Historical 60/600-second records retain
their original source and methodology. No later implementation change silently
updates those records or extends their scope of inference.
