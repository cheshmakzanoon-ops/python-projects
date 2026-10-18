import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pp_resonance.analysis import analyze, analyze_chunks
from pp_resonance.model import FrameConfig
from pp_resonance.streaming.framing import Framer
from pp_resonance.synthesis.tones import clean_plucks, render


@given(st.lists(st.integers(min_value=0, max_value=4096), min_size=1, max_size=15))
@settings(max_examples=35, deadline=None)
def test_chunk_frames_match_independent_padding(sizes: list[int]) -> None:
    count = sum(sizes)
    audio = np.sin(np.arange(count) * 0.031)
    framer = Framer()
    observed = []
    offset = 0
    for size in sizes:
        observed.extend(framer.feed(audio[offset : offset + size]))
        offset += size
    observed.extend(framer.feed(np.empty(0), final=True))
    assert [s for s, _ in observed] == list(range(0, count, 256))
    for start, values in observed:
        expected = np.zeros(2048)
        section = audio[start : start + 2048]
        expected[: len(section)] = section
        np.testing.assert_array_equal(values, expected)
    assert framer.peak_buffer_samples <= max(sizes) + 2047
    assert len(framer.buffer) == 0
    with pytest.raises(ValueError):
        list(framer.feed(np.empty(0)))


def test_RE03_randomized_chunk_entire_analysis_identical() -> None:
    audio = render(clean_plucks(), 44100, round(4.9 * 44100))
    expected = analyze(audio, 44100)
    for seed in range(4):
        rng = np.random.default_rng(seed)
        sections = []
        index = 0
        while index < len(audio):
            size = int(rng.integers(1, 5000))
            sections.append(audio[index : index + size])
            index += size
        actual = analyze_chunks(sections, 44100)
        assert actual.pitches == expected.pitches
        assert actual.notes == expected.notes
        assert actual.onsets == expected.onsets
        assert actual.sample_count == expected.sample_count


def test_invalid_framing() -> None:
    with pytest.raises(ValueError):
        FrameConfig(size=200)
    with pytest.raises(ValueError):
        FrameConfig(hop=0)
    with pytest.raises(ValueError):
        list(Framer().feed(np.array([np.nan])))
    with pytest.raises(ValueError):
        list(Framer().feed(np.zeros((2, 2))))
