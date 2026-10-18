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
    events = []
    last = -rate
    global_floor = max(1e-8, float(np.max(values)) * 0.08)
    for i in range(1, len(values) - 1):
        baseline = float(np.median(values[max(0, i - 8) : i + 9]))
        threshold = max(global_floor, 1.5 * baseline)
        rising = energies is None or energies[i] > energies[i - 1] * 1.001
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
