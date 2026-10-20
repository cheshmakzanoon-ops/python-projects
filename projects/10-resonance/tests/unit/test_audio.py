from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from pp_resonance.analysis import analyze, analyze_chunks
from pp_resonance.audio_io.pcm import blocks, mono
from pp_resonance.model import AudioSpec
from pp_resonance.synthesis.tones import Tone, chunks, render


def test_RE02_silence_short_clipping_rates_and_antiphase_stereo() -> None:
    silence = analyze(np.zeros(48000), 48000)
    assert not silence.notes and not silence.onsets
    assert all(p.frequency is None for p in silence.pitches)
    for count in (0, 1, 20, 1000):
        short = analyze(np.ones(count) * 0.5, 48000)
        assert not short.notes
        assert any("short" in d for d in short.diagnostics)
    audio = render([Tone(52, 0, 0.5)], 48000, 24000)
    stereo = np.column_stack((audio, -audio))
    result = analyze(stereo, 48000)
    assert result.notes
    np.testing.assert_array_equal(mono(stereo)[0], audio)
    assert any("stereo" in d for d in result.diagnostics)
    clipped = analyze(np.clip(audio * 10, -1, 1), 48000)
    assert any("clipping" in d for d in clipped.diagnostics)
    with pytest.raises(ValueError):
        AudioSpec(22050)
    with pytest.raises(ValueError):
        AudioSpec(48000, 3)
    with pytest.raises(ValueError):
        analyze(np.zeros(48000), 96000)
    with pytest.raises(ValueError):
        mono(np.array([np.inf]))
    with pytest.raises(ValueError):
        mono(np.zeros((4, 3)))
    with pytest.raises(ValueError):
        analyze_chunks([stereo], 48000)


def test_file_io_channel_choice_stays_fixed(tmp_path: Path) -> None:
    audio = np.column_stack((np.sin(np.arange(10000) * 0.05) * 0.5, np.zeros(10000)))
    path = tmp_path / "stereo.wav"
    sf.write(path, audio, 44100, subtype="FLOAT")
    spec, parts = blocks(path, 2000)
    assert spec.channels == 2
    observed = np.concatenate(list(parts))
    np.testing.assert_allclose(observed, audio[:, 0], atol=2e-8)
    with pytest.raises(ValueError):
        blocks(path, 0)


def test_synthesis_chunk_invariance() -> None:
    tones = [Tone(50, 0.2, 0.4, vibrato_cents=20, bend_cents=100)]
    expected = render(tones, 48000, 48000, noise=0.001)
    observed = np.concatenate(list(chunks(tones, 48000, 1, 1234, noise=0.001)))
    np.testing.assert_array_equal(expected, observed)


def test_fixed_denominator_challenge_metrics_include_misses_and_silence() -> None:
    from pp_resonance.metrics.evaluate import note_metrics, trajectory_metrics
    from pp_resonance.model import PitchFrame

    tone = Tone(69, 0.1, 0.4)
    frames = [
        PitchFrame(9984, 11008, 440, 0.99, 0.2, "voiced"),
        PitchFrame(13056, 14080, None, 0, 0.2, "uncertain"),
        PitchFrame(29952, 30976, 440, 0.9, 0.01, "voiced"),
    ]
    metrics = trajectory_metrics(frames, [tone], 48000, sample_count=48000)
    assert metrics["eligible_voiced_frames"] == 47
    assert metrics["voiced_misses"] == 46
    assert metrics["false_voiced_silence_frames"] == 1
    assert metrics["within_10_cents_all_eligible"] == 1 / 47
    assert note_metrics([], [tone], 48000)["misses"] == 1


def test_nondefault_configuration_is_preserved_in_report() -> None:
    from pp_resonance.model import AnalysisConfig, FrameConfig
    from pp_resonance.reports.render import report_json

    config = AnalysisConfig(frame=FrameConfig(size=4096, hop=512), silence_rms=0.002)
    result = analyze(np.zeros(10000), 48000, config)
    data = report_json(result, {})
    assert result.config == config
    assert data["config"] == {
        "frame": {"size": 4096, "hop": 512},
        "threshold": 0.15,
        "silence_rms": 0.002,
        "minimum_confidence": 0.8,
    }
    assert data["timing"]["lookahead_samples"] == 4096


def test_onset_metrics_count_unmatched_events() -> None:
    from pp_resonance.metrics.evaluate import onset_metrics

    result = onset_metrics([4800, 24000], [Tone(60, 0.1, 0.2), Tone(64, 0.9, 0.1)], 48000)
    assert result["misses"] == result["extras"] == 1
    assert result["mean_abs_error_seconds"] == 0


def test_report_preview_uses_streaming_channel_and_bounded_duration(tmp_path: Path) -> None:
    from pp_resonance.audio_io.pcm import preview

    path = tmp_path / "audio.wav"
    audio = np.column_stack((np.ones(96000) * 0.25, np.ones(96000) * -0.1))
    sf.write(path, audio, 48000, subtype="FLOAT")
    clip = preview(path, seconds=1)
    assert clip.shape == (48000,)
    np.testing.assert_array_equal(clip, np.ones(48000) * 0.25)
    with pytest.raises(ValueError):
        preview(path, 31)
