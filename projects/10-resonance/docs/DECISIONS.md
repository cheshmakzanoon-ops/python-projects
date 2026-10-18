# Decisions

* Fixed overlap YIN rather than shrinking autocorrelation: all lags compare the same number of samples, avoiding lag-dependent bias. FFT correlation replaces only the dot-product kernel; an explicit direct-sum oracle checks its indexing.
* Energetic stereo channel rather than a stereo mean: anti-phase mono content would disappear on averaging. The array API chooses globally with left tie-break; file streaming chooses once from its first second and retains that channel. It does not separate instruments; alternate-channel quality is outside this policy.
* Silence abstention rather than guessed notes: RMS <.003 or insufficient periodicity is unvoiced. RE-01 counts every abstention as failure, so the clean-grid score cannot improve by selective omission.
* Integer sample authority rather than accumulated floating seconds: randomized chunks give identical timestamps, frames and estimates; output time conversion occurs only for presentation/MIDI.
* Edit alignment rather than greedy pitch matching: insertion and omission remain explicit without forcing distant pitches into reference matches. O(nm) memory is acceptable for the ~800-event standard fixture; hour-long scores would warrant banding/checkpointed traceback.
* Offline note segmentation rather than a pretrained transcription model: this exposes uncertainty and failure semantics; universal polyphonic transcription is excluded.
* Source digests rather than a bare Git hash: development evidence honestly identifies dirty snapshots. Final evidence must be regenerated on the coordinator's immutable committed export.

* Repeated-pitch articulation needs onset evidence: a sustained pitch trajectory alone cannot distinguish two adjacent same-pitch attacks. Credible attacks split events, while smooth bend/vibrato trajectories remain one event absent a new attack.
* Reject sub-tick MIDI events: rounding can collapse a valid sample interval to one tick position, making note ordering impossible. Raising a clear error before writing preserves both MIDI validity and an existing output file. Explicit positive tempos are checked independently instead of assuming the default tempo.
