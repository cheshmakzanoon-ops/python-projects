"""Adaptive spectral-flux peaks with a finite lookahead and refractory interval."""

import numpy as np

from pp_resonance.model import OnsetEvent


def detect(
    fluxes: list[float],
    starts: list[int],
    rate: int,
    size: int,
    energies: list[float] | None = None,
) -> list[OnsetEvent]:
    if not fluxes:
        return []
    values = np.asarray(fluxes)
    # Frame RMS contains pitch-period ripple, especially near the low-frequency
    # bound. Smooth adjacent frames before asking whether the envelope rises;
    # the extra one-frame horizon is inside the adaptive threshold's horizon.
    envelope = np.convolve(energies, np.ones(3) / 3, mode="same") if energies is not None else None
    events = []
    last = -rate
    for i in range(1, len(values) - 1):
        neighborhood = values[max(0, i - 8) : i + 9]
        baseline = float(np.median(neighborhood))
        # All adaptation shares the declared eight-frame horizon. A distant
        # loud attack must not retrospectively erase an earlier quiet attack.
        floor = max(1e-8, float(np.max(neighborhood)) * 0.08)
        threshold = max(floor, 1.5 * baseline)
        rising = envelope is None or envelope[i] > envelope[i - 1] * 1.001
        if (
            rising
            and values[i] > threshold
            and values[i] >= values[i - 1]
            and values[i] > values[i + 1]
        ):
            sample = max(0, starts[i] + size // 2)
            if sample - last >= int(0.10 * rate):
                events.append(OnsetEvent(sample, float(min(1, values[i] / (threshold * 4)))))
                last = sample
    return events
