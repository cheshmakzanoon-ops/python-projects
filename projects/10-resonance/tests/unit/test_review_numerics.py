import math

import pytest

from pp_resonance.metrics.evaluate import trajectory_metrics
from pp_resonance.model import PitchFrame
from pp_resonance.notes.decode import cents
from pp_resonance.synthesis.tones import Tone


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 0, -1])
def test_cents_rejects_nonfinite_or_unvoiced_frequencies(value: float) -> None:
    with pytest.raises(ValueError):
        cents(value, 440)
    with pytest.raises(ValueError):
        cents(440, value)


def test_cents_remains_finite_for_finite_extreme_frequencies() -> None:
    assert cents(1e308, 1e-308) == pytest.approx(1200 * (math.log2(1e308) - math.log2(1e-308)))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0.0, -440.0])
def test_trajectory_metrics_count_invalid_estimates_as_misses(value: float) -> None:
    frame = PitchFrame(10000, 11024, value, 0.9, 0.2, "voiced")
    result = trajectory_metrics([frame], [Tone(69, 0.1, 0.4)], 48000)
    assert result["eligible_voiced_frames"] == 1
    assert result["voiced_misses"] == 1
    assert result["voicing_recall"] == 0
    assert result["within_10_cents_all_eligible"] == 0
