import json
import sys
from pathlib import Path

import pytest

from pp_resonance.alignment.dynamic import load_score
from pp_resonance.cli import main
from pp_resonance.formats import MAX_JSON_BYTES, read_json


@pytest.mark.parametrize(
    "document",
    [
        [],
        None,
        {"schema_version": True},
        {"schema_version": 1, "units": "seconds", "notes": [None], "tempo_bpm": 120},
    ],
)
def test_malformed_score_shapes_raise_controlled_errors(tmp_path: Path, document: object) -> None:
    path = tmp_path / "score.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_score(path, 48000)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tempo_bpm", True),
        ("tempo_bpm", "120"),
        ("onset", True),
        ("duration", 10**400),
        ("onset", float("inf")),
    ],
)
def test_score_numbers_must_be_finite_numeric_values(
    tmp_path: Path, field: str, value: object
) -> None:
    data = {
        "schema_version": 1,
        "units": "seconds",
        "tempo_bpm": 120,
        "notes": [{"id": "r", "midi": 60, "onset": 0, "duration": 1}],
    }
    if field == "tempo_bpm":
        data[field] = value
    else:
        data["notes"][0][field] = value
    path = tmp_path / "score.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_score(path, 48000)


def test_oversized_json_is_rejected_without_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "large.json"
    with path.open("wb") as stream:
        stream.truncate(MAX_JSON_BYTES + 1)

    def refuse_read(*args: object, **kwargs: object) -> None:
        pytest.fail("oversized JSON must be rejected before opening")

    monkeypatch.setattr(Path, "open", refuse_read)
    with pytest.raises(ValueError, match="bytes"):
        read_json(path)


def test_deep_json_has_a_controlled_error(tmp_path: Path) -> None:
    path = tmp_path / "deep.json"
    path.write_text("[" * 2000 + "0" + "]" * 2000)
    with pytest.raises(ValueError, match="deeply nested"):
        read_json(path)


def test_score_note_count_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "score.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "units": "seconds",
                "tempo_bpm": 120,
                "notes": [{"id": "r", "midi": 60, "onset": 0, "duration": 1}] * 10001,
            }
        )
    )
    with pytest.raises(ValueError, match="notes"):
        load_score(path, 48000)


def test_json_pipe_is_rejected_before_opening(tmp_path: Path) -> None:
    import os

    path = tmp_path / "input.json"
    os.mkfifo(path)
    with pytest.raises(ValueError, match="regular file"):
        read_json(path)


@pytest.mark.parametrize(
    "document",
    [
        "[]",
        "null",
        '{"schema_version":1,"notes":null}',
        '{"schema_version":1,"notes":[null]}',
        '{"schema_version":true,"notes":[]}',
        '{"schema_version":1,"notes":[],"sample_rate":NaN}',
    ],
)
def test_export_malformed_json_is_a_cli_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    document: str,
) -> None:
    source = tmp_path / "analysis.json"
    source.write_text(document)
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys, "argv", ["resonance", "export", "--input", str(source), "--output", str(output)]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "resonance:" in capsys.readouterr().err
    assert not (output / "transcription.mid").exists()
