import json
import subprocess
import sys
from pathlib import Path

import mido
import pytest

from pp_resonance.alignment.dynamic import load_score
from pp_resonance.cli import clean, prepare, save_demo
from pp_resonance.midi.export import check_bytes, export
from pp_resonance.model import NoteEvent


def test_RE07_RE08_playable_report_midi_json_real_interfaces(tmp_path: Path) -> None:
    output = prepare(tmp_path / "demo")
    result = save_demo(output, 1729)
    assert result["notes"] == result["midi_checked"] == 6
    data = json.loads((output / "analysis.json").read_text())
    assert data["schema_version"] == 1
    assert data["provenance"]["source_content_sha256"]
    report = (output / "analysis.html").read_text()
    for part in (
        "<audio controls",
        "data:audio/wav;base64,",
        "data:image/png;base64,",
        "pitch-trajectory",
        "transcription.mid",
        "Confidence",
        "cents",
    ):
        assert part in report
    checked = check_bytes(output / "transcription.mid")
    midi = mido.MidiFile(output / "transcription.mid")
    assert midi.ticks_per_beat == 480
    assert any(m.type == "set_tempo" and m.tempo == 500000 for m in midi.tracks[0])
    for actual, expected in zip(checked, data["notes"], strict=True):
        pitch, start, end = actual
        assert pitch == expected["midi"]
        assert abs(start / 960 - expected["start"] / 48000) <= 0.5 / 960
        assert abs(end / 960 - expected["end"] / 48000) <= 0.5 / 960
    assert len(load_score(output / "reference.json", 48000)) == 6
    extra = output / "user.txt"
    extra.write_text("preserve me")
    clean(output)
    assert extra.read_text() == "preserve me"
    assert list(output.iterdir()) == [extra]


def test_cli_subprocess_and_safe_owned_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "cli"
    command = [
        sys.executable,
        "-m",
        "pp_resonance.cli",
        "demo",
        "--output",
        str(path),
        "--seed",
        "1729",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["notes"] == 6
    result = subprocess.run(
        [sys.executable, "-m", "pp_resonance.cli", "clean-demo", "--output", str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0 and not path.exists()
    unowned = tmp_path / "personal"
    unowned.mkdir()
    (unowned / "keep.txt").write_text("safe")
    with pytest.raises(ValueError):
        prepare(unowned)
    with pytest.raises(ValueError):
        clean(unowned)
    with pytest.raises(ValueError):
        prepare(Path("relative"))
    with pytest.raises(ValueError):
        clean(Path("relative"))
    owned = prepare(tmp_path / "owned")
    (owned / "audio.wav").symlink_to(unowned / "keep.txt")
    with pytest.raises(ValueError):
        prepare(owned)
    with pytest.raises(ValueError):
        clean(owned)
    assert (unowned / "keep.txt").read_text() == "safe"


def test_reference_and_midi_failures(tmp_path: Path) -> None:
    score = tmp_path / "bad.json"
    score.write_text('{"schema_version":99}')
    with pytest.raises(ValueError):
        load_score(score, 48000)
    score.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "units": "beats",
                "tempo_bpm": 120,
                "notes": [{"id": "r", "midi": 60, "onset": 2, "duration": 1}],
            }
        )
    )
    note = load_score(score, 48000)[0]
    assert (note.start, note.end) == (48000, 72000)
    bad = NoteEvent("bad", 60, 100, 0, 440, 1, 0)
    with pytest.raises(ValueError):
        export(tmp_path / "bad.mid", [bad], 48000)
    path = tmp_path / "broken.mid"
    path.write_bytes(b"not midi")
    with pytest.raises(ValueError):
        check_bytes(path)


def test_all_user_file_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from pp_resonance.cli import main

    def run(*arguments: str) -> dict[str, object]:
        monkeypatch.setattr(sys, "argv", ["resonance", *arguments])
        main()
        value: dict[str, object] = json.loads(capsys.readouterr().out)
        return value

    synth = tmp_path / "synthesis"
    result = run("synthesize", "--output", str(synth))
    assert Path(str(result["audio"])).is_file()
    analysis = tmp_path / "analysis"
    result = run("analyze", "--input", str(synth / "audio.wav"), "--output", str(analysis))
    assert result["notes"] == 6
    score = tmp_path / "score.json"
    score.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "units": "seconds",
                "tempo_bpm": 120,
                "notes": [{"id": "first", "midi": 40, "onset": 0.3, "duration": 0.42}],
            }
        )
    )
    aligned = tmp_path / "aligned"
    run(
        "align",
        "--input",
        str(synth / "audio.wav"),
        "--score",
        str(score),
        "--output",
        str(aligned),
    )
    assert json.loads((aligned / "analysis.json").read_text())["alignment"]
    result = run(
        "export", "--input", str(analysis / "analysis.json"), "--output", str(tmp_path / "midi")
    )
    assert result["midi_notes_checked"] == 6
    result = run("compare", "--output", str(tmp_path / "compare"))
    assert result["eligible_frames"] == 6272
    monkeypatch.setattr(sys, "argv", ["resonance", "clean-demo", "--output", str(analysis)])
    main()
    assert not analysis.exists()
    capsys.readouterr()
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version":99}')
    monkeypatch.setattr(
        sys,
        "argv",
        ["resonance", "export", "--input", str(invalid), "--output", str(tmp_path / "bad")],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_independent_midi_checker_rejects_corrupt_lifecycles(tmp_path: Path) -> None:
    import struct

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    tempo = b"\x00\xff\x51\x03\x07\xa1\x20"
    ending = b"\x00\xff\x2f\x00"
    cases = [
        ending,  # tempo absent
        tempo,  # end marker absent
        tempo + b"\x00\x90\x3c\x5a" + ending,  # missing note-off
        tempo + b"\x00\x80\x3c\x00" + ending,  # unmatched note-off
        tempo + b"\x00\x90\x3c\x5a\x00\x90\x3c\x5a" + ending,
        tempo + b"\x00\xb0\x00\x00" + ending,
        b"\x80\x80\x80\x80",
        tempo + b"\x80",
        tempo + b"\x00",
        tempo + b"\x00\xff",
        tempo + b"\x00\xff\x51\x03\x07",
        tempo + b"\x00\x90\x3c",
        b"\x00\xff\x51\x03\x00\x00\x00" + ending,
    ]
    for index, payload in enumerate(cases):
        path = tmp_path / f"bad{index}.mid"
        path.write_bytes(header + b"MTrk" + len(payload).to_bytes(4, "big") + payload)
        with pytest.raises(ValueError):
            check_bytes(path)
    path = tmp_path / "length.mid"
    path.write_bytes(header + b"MTrk\x00\x00\x00\xff" + ending)
    with pytest.raises(ValueError):
        check_bytes(path)
    with pytest.raises(ValueError):
        export(tmp_path / "tempo.mid", [], 48000, tempo=0)


def test_midi_subtick_rejection_preserves_file_and_custom_tempo_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "subtick.mid"
    path.write_bytes(b"preserve existing output")
    tiny = NoteEvent("tiny", 60, 0, 1, 261.6, 1, 0)
    with pytest.raises(ValueError, match="less than one MIDI tick"):
        export(path, [tiny], 48000)
    assert path.read_bytes() == b"preserve existing output"
    note = NoteEvent("custom", 60, 4800, 52800, 261.6, 1, 0)
    export(path, [note], 48000, tempo=600000)
    checked = check_bytes(path)
    assert checked == [(60, 80, 880)]
    parsed = mido.MidiFile(path)
    assert any(
        message.type == "set_tempo" and message.tempo == 600000 for message in parsed.tracks[0]
    )
    assert parsed.length == pytest.approx(1.1)
