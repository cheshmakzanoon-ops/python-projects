import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from pp_resonance.alignment.dynamic import load_score
from pp_resonance.cli import OWNER, clean, main, prepare
from pp_resonance.midi.export import check_bytes, export
from pp_resonance.model import NoteEvent


def test_cleanup_checks_all_targets_before_deleting_anything(tmp_path: Path) -> None:
    output = prepare(tmp_path / "output")
    audio = output / "audio.wav"
    audio.write_bytes(b"keep generated audio after failed cleanup")
    external = tmp_path / "external"
    external.write_text("keep external")
    (output / "transcription.mid").symlink_to(external)
    before = audio.read_bytes()
    with pytest.raises(ValueError, match="symlink"):
        clean(output)
    assert audio.read_bytes() == before
    assert (output / OWNER).is_file()
    assert external.read_text() == "keep external"


def test_cleanup_rejects_a_symlink_ownership_marker(tmp_path: Path) -> None:
    external = tmp_path / "marker"
    external.write_text(json.dumps({"owner": "pp-resonance", "version": 1}))
    output = tmp_path / "unowned"
    output.mkdir()
    (output / OWNER).symlink_to(external)
    audio = output / "audio.wav"
    audio.write_bytes(b"user audio")
    with pytest.raises(ValueError, match="symlink|unowned"):
        clean(output)
    assert audio.read_bytes() == b"user audio"
    assert (output / OWNER).is_symlink()


@pytest.mark.parametrize("command", ["analyze", "align", "export"])
def test_cli_refuses_to_overwrite_input_before_preparing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    output = prepare(tmp_path / "output")
    target = "transcription.mid" if command == "export" else "audio.wav"
    audio = output / target
    if command == "export":
        audio.write_text(json.dumps({"schema_version": 1, "sample_rate": 48000, "notes": []}))
    else:
        sf.write(audio, np.zeros(32), 48000, subtype="PCM_16")
    original = {path.name: path.read_bytes() for path in output.iterdir()}
    argv = ["resonance", command, "--input", str(audio), "--output", str(output)]
    if command == "align":
        score = tmp_path / "score.json"
        score.write_text(
            json.dumps({"schema_version": 1, "units": "seconds", "tempo_bpm": 120, "notes": []})
        )
        argv.extend(["--score", str(score)])
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert {path.name: path.read_bytes() for path in output.iterdir()} == original


def test_invalid_audio_is_a_cli_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    audio = tmp_path / "broken.wav"
    audio.write_bytes(b"not encoded audio")
    monkeypatch.setattr(
        sys,
        "argv",
        ["resonance", "analyze", "--input", str(audio), "--output", str(tmp_path / "output")],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "resonance:" in capsys.readouterr().err


@pytest.mark.parametrize("overlap", ["hardlink", "score"])
def test_cli_preserves_inputs_that_alias_other_output_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overlap: str
) -> None:
    output = prepare(tmp_path / "output")
    audio = tmp_path / "input.wav"
    sf.write(audio, np.zeros(32), 48000, subtype="PCM_16")
    argv = ["resonance", "analyze", "--input", str(audio), "--output", str(output)]
    if overlap == "hardlink":
        (output / "audio.wav").hardlink_to(audio)
    else:
        score = output / "analysis.json"
        score.write_text(
            json.dumps({"schema_version": 1, "units": "seconds", "tempo_bpm": 120, "notes": []})
        )
        argv.extend(["--score", str(score)])
    original = {path.name: path.read_bytes() for path in output.iterdir()}
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert {path.name: path.read_bytes() for path in output.iterdir()} == original


@pytest.mark.parametrize(
    "payload",
    [
        b"\x00\xff\x2f\x01\x00",  # end-of-track payload must be empty
        b"\x00\xff\x2f\x00\x00\xff\x2f\x00",  # no events may follow the end
        b"\x00\x90\x80\x5a\x01\x80\x80\x00\x00\xff\x2f\x00",  # invalid pitch
        b"\x00\x90\x3c\x80\x01\x80\x3c\x00\x00\xff\x2f\x00",  # invalid velocity
        b"\x00\x90\x3c\x5a\x00\x80\x3c\x00\x00\xff\x2f\x00",  # zero duration
    ],
)
def test_independent_midi_checker_rejects_invalid_standard_midi(
    tmp_path: Path, payload: bytes
) -> None:
    payload = b"\x00\xff\x51\x03\x07\xa1\x20" + payload
    path = tmp_path / "bad.mid"
    path.write_bytes(
        b"MThd"
        + struct.pack(">IHHH", 6, 0, 1, 480)
        + b"MTrk"
        + len(payload).to_bytes(4, "big")
        + payload
    )
    with pytest.raises(ValueError):
        check_bytes(path)


def test_midi_delta_outside_standard_range_preserves_existing_output(tmp_path: Path) -> None:
    path = tmp_path / "long.mid"
    path.write_bytes(b"keep prior output")
    start = (0x0FFFFFFF + 1) * 50  # default tempo: 50 samples per tick at 48 kHz
    note = NoteEvent("late", 60, start, start + 48000, 261.6, 1, 0)
    with pytest.raises(ValueError, match="delta|28-bit"):
        export(path, [note], 48000)
    assert path.read_bytes() == b"keep prior output"


def test_midi_half_ticks_round_exactly_to_even(tmp_path: Path) -> None:
    # At 48 kHz/default tempo, samples 3,075 and 51,075 are exactly
    # ticks 61.5 and 1,021.5. Floating arithmetic used to round both down.
    path = tmp_path / "ties.mid"
    export(path, [NoteEvent("tie", 60, 3075, 51075, 261.6, 1, 0)], 48000)
    assert check_bytes(path) == [(60, 62, 1022)]


def test_reference_duration_must_survive_sample_quantization(tmp_path: Path) -> None:
    score = tmp_path / "tiny.json"
    score.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "units": "seconds",
                "tempo_bpm": 120,
                "notes": [{"id": "tiny", "midi": 60, "onset": 0, "duration": 1e-12}],
            }
        )
    )
    with pytest.raises(ValueError, match="sample|quantiz"):
        load_score(score, 48000)
