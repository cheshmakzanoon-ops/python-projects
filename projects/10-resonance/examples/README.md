# Reference-score input

reference.json demonstrates schema 1 with explicit beat units and 120 BPM (one beat =0.5 seconds). Note IDs are unique, pitches are MIDI integers, and onset/duration map to integer audio samples with rounding. Use `analyze --input guitar.wav --score examples/reference.json --output ABS`. Demo-generated reference.json instead uses seconds and has its exact six-pluck annotations.
