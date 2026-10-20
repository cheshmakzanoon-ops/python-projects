# Recorded sample outputs

The retained [MIDI file](transcription.mid) comes from the seeded synthetic demo.
Its historical [sample manifest](sample-manifest.json) records note events,
artifact hashes and the exact development-source provenance. That run's PNG,
HTML and audio are not bundled here. Generate current plots and a playable report
from the project directory:

```sh
uv run --locked resonance demo --output /tmp/resonance-sample --seed 1729
```

The generated output contains `analysis.png`, `analysis.html`, `audio.wav` and a
new transcription. These synthetic fixtures are not a recorded guitarist or an
accuracy claim for real instruments.

[Development verification](development-verification.json) records the original
25-test interpreter matrix and coverage. [Development CI benchmark](development-ci-benchmark.json)
contains the five-repeat 60-second workload, source/environment hashes and
challenge errors. Both retain their actual dirty development-source identifiers;
[verification history](../docs/VERIFICATION.md) distinguishes later checks and
immutable benchmark records.
