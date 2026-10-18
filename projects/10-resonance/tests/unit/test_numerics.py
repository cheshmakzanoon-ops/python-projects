import numpy as np
import pytest
from scipy import signal

from pp_resonance.pitch.difference import difference, normalize
from pp_resonance.spectral.transforms import inverse, padded, stft, window


def test_yin_difference_matches_explicit_fixed_overlap() -> None:
    rng = np.random.default_rng(18)
    samples = rng.normal(size=1024)
    maximum = 150
    expected = np.array(
        [np.sum((samples[:874] - samples[lag : lag + 874]) ** 2) for lag in range(maximum + 1)]
    )
    np.testing.assert_allclose(difference(samples, maximum), expected, atol=2e-12)
    normalized = normalize(expected)
    assert normalized[0] == 1
    for lag in (1, 30, 149):
        assert normalized[lag] == pytest.approx(expected[lag] / np.mean(expected[1 : lag + 1]))
    assert np.all(normalize(np.zeros(100)) == 1)
    with pytest.raises(ValueError):
        difference(samples, 1024)


def test_RE04_stft_reconstruction_and_independent_scipy() -> None:
    rng = np.random.default_rng(1729)
    audio = rng.normal(size=13791)
    spectrum = stft(audio)
    reconstructed = inverse(spectrum, len(audio))
    np.testing.assert_allclose(reconstructed, audio, rtol=0, atol=1e-11)
    _, _, reference = signal.stft(
        padded(audio, 2048, 512),
        fs=48000,
        window=window(2048),
        nperseg=2048,
        noverlap=1536,
        boundary=None,
        padded=False,
    )
    np.testing.assert_allclose(spectrum, reference.T * np.sum(window(2048)), rtol=0, atol=1e-10)
    _, scipy_inverse = signal.istft(
        reference, fs=48000, window=window(2048), nperseg=2048, noverlap=1536, boundary=False
    )
    np.testing.assert_allclose(
        scipy_inverse[2048 : 2048 + len(audio)], reconstructed, rtol=0, atol=1e-11
    )
    with pytest.raises(ValueError):
        stft(audio, hop=4096)


def test_configuration_and_low_confidence_are_explicit() -> None:
    from pp_resonance.model import AnalysisConfig
    from pp_resonance.pitch.difference import estimate

    with pytest.raises(ValueError):
        AnalysisConfig(threshold=2)
    with pytest.raises(ValueError):
        AnalysisConfig(silence_rms=0)
    samples = np.sin(np.arange(2048) * 0.05) + 0.05 * np.random.default_rng(12).normal(size=2048)
    result = estimate(samples, 48000, 0, AnalysisConfig(minimum_confidence=1))
    assert result.frequency is None and result.reason == "low confidence"
