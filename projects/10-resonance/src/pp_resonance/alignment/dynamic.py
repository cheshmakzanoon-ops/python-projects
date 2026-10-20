"""Monotone edit alignment, keeping missing and inserted notes explicit."""

import math
from pathlib import Path

import numpy as np

from pp_resonance.formats import read_json
from pp_resonance.model import AlignedNote, AudioSpec, NoteEvent, ReferenceNote

MAX_SCORE_NOTES = 10_000
MAX_ALIGNMENT_CELLS = 4_000_000


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} exceeds finite range") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def load_score(path: Path, rate: int) -> list[ReferenceNote]:
    AudioSpec(rate)
    data = read_json(path)
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
        or data.get("units") not in ("seconds", "beats")
        or not isinstance(data.get("notes"), list)
    ):
        raise ValueError("Require score schema_version=1 and seconds or beats units")
    if len(data["notes"]) > MAX_SCORE_NOTES:
        raise ValueError(f"Score exceeds {MAX_SCORE_NOTES} notes; split it into phrases")
    tempo = _number(data.get("tempo_bpm"), "tempo_bpm")
    if tempo <= 0:
        raise ValueError("tempo_bpm must be positive")
    scale = 60 / tempo if data["units"] == "beats" else 1.0
    result = []
    ids = set()
    for n in data["notes"]:
        if (
            not isinstance(n, dict)
            or not {"id", "midi", "onset", "duration"} <= n.keys()
            or any(
                isinstance(n[key], bool) or not isinstance(n[key], (int, float))
                for key in ("onset", "duration")
            )
            or type(n["midi"]) is not int
        ):
            raise ValueError("Invalid reference note fields")
        start = _number(n["onset"], "onset")
        duration = _number(n["duration"], "duration")
        pitch = n["midi"]
        if (
            not math.isfinite(start)
            or not math.isfinite(duration)
            or not isinstance(n["id"], str)
            or not n["id"]
            or len(n["id"]) > 200
            or start < 0
            or duration <= 0
            or not 0 <= pitch <= 127
            or n["id"] in ids
        ):
            raise ValueError("Invalid or duplicate reference note")
        ids.add(n["id"])
        onset_samples, end_samples = start * scale * rate, (start + duration) * scale * rate
        if not math.isfinite(onset_samples) or not math.isfinite(end_samples):
            raise ValueError("Reference times exceed finite sample range")
        onset_sample, end_sample = round(onset_samples), round(end_samples)
        if end_sample <= onset_sample:
            raise ValueError("Reference note duration quantizes to less than one sample")
        result.append(
            ReferenceNote(
                n["id"],
                pitch,
                onset_sample,
                end_sample,
            )
        )
    if any(a.start > b.start for a, b in zip(result, result[1:])):
        raise ValueError("Score must be ordered by onset")
    return result


def align(
    reference: list[ReferenceNote],
    detected: list[NoteEvent],
    rate: int,
    tempo_scale: float = 1.0,
    *,
    max_cells: int = MAX_ALIGNMENT_CELLS,
) -> list[AlignedNote]:
    AudioSpec(rate)
    if not 0.5 <= _number(tempo_scale, "tempo_scale") <= 2:
        raise ValueError("Tempo scale outside [0.5,2]")
    rows, cols = len(reference), len(detected)
    if type(max_cells) is not int or max_cells <= 0:
        raise ValueError("Alignment cell budget must be a positive integer")
    if (rows + 1) * (cols + 1) > max_cells:
        raise ValueError(
            f"Alignment exceeds {max_cells} cells; split the phrase or raise the explicit budget"
        )
    for events in (reference, detected):
        ids: set[str] = set()
        previous_start: int | None = None
        for event in events:
            if (
                not isinstance(event.id, str)
                or not event.id
                or event.id in ids
                or type(event.midi) is not int
                or not 0 <= event.midi <= 127
                or type(event.start) is not int
                or type(event.end) is not int
                or event.end <= event.start
                or previous_start is not None
                and event.start < previous_start
            ):
                raise ValueError("Alignment requires ordered integer note events with unique IDs")
            if isinstance(event, NoteEvent):
                _number(event.cents, "cents")
                if not 0 <= _number(event.confidence, "confidence") <= 1:
                    raise ValueError("Alignment requires confidence in [0,1]")
            ids.add(event.id)
            previous_start = event.start
    dp = np.zeros((rows + 1, cols + 1))
    operations = np.zeros((rows + 1, cols + 1), dtype=np.int8)
    dp[:, 0] = np.arange(rows + 1) * 1.2
    dp[0, :] = np.arange(cols + 1) * 1.2
    operations[:, 0] = 1
    operations[0, :] = 2
    for i, ref in enumerate(reference, 1):
        for j, note in enumerate(detected, 1):
            # Low-confidence estimates cannot become authoritative matches.
            match = (
                abs(ref.midi - note.midi) * 1.5
                + min(2, abs(ref.start * tempo_scale - note.start) / rate)
                + (3 if note.confidence < 0.8 else 0)
            )
            costs = (dp[i - 1, j - 1] + match, dp[i - 1, j] + 1.2, dp[i, j - 1] + 1.2)
            operation = int(np.argmin(costs))
            dp[i, j], operations[i, j] = costs[operation], operation
    result = []
    i, j = rows, cols
    while i or j:
        operation = int(operations[i, j])
        if operation == 0:
            ref, note = reference[i - 1], detected[j - 1]
            result.append(
                AlignedNote(
                    ref.id,
                    note.id,
                    float(dp[i, j] - dp[i - 1, j - 1]),
                    note.start - round(ref.start * tempo_scale),
                    (note.midi - ref.midi) * 100 + note.cents,
                )
            )
            i, j = i - 1, j - 1
        elif operation == 1:
            result.append(AlignedNote(reference[i - 1].id, None, 1.2, None, None))
            i -= 1
        else:
            result.append(AlignedNote(None, detected[j - 1].id, 1.2, None, None))
            j -= 1
    return result[::-1]
