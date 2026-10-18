"""Monotone edit alignment, keeping missing and inserted notes explicit."""

import json
import math
from pathlib import Path

import numpy as np

from pp_resonance.model import AlignedNote, AudioSpec, NoteEvent, ReferenceNote


def load_score(path: Path, rate: int) -> list[ReferenceNote]:
    AudioSpec(rate)
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or data.get("units") not in ("seconds", "beats"):
        raise ValueError("Require score schema_version=1 and seconds or beats units")
    tempo = float(data["tempo_bpm"])
    if not math.isfinite(tempo) or tempo <= 0:
        raise ValueError("tempo_bpm must be positive")
    scale = 60 / tempo if data["units"] == "beats" else 1.0
    result = []
    ids = set()
    for n in data["notes"]:
        start, duration, pitch = float(n["onset"]), float(n["duration"]), int(n["midi"])
        if (
            not math.isfinite(start)
            or not math.isfinite(duration)
            or not isinstance(n["id"], str)
            or not n["id"]
            or not isinstance(n["midi"], int)
            or isinstance(n["midi"], bool)
            or start < 0
            or duration <= 0
            or not 0 <= pitch <= 127
            or n["id"] in ids
        ):
            raise ValueError("Invalid or duplicate reference note")
        ids.add(n["id"])
        result.append(
            ReferenceNote(
                n["id"],
                pitch,
                round(start * scale * rate),
                round((start + duration) * scale * rate),
            )
        )
    if any(a.start > b.start for a, b in zip(result, result[1:])):
        raise ValueError("Score must be ordered by onset")
    return result


def align(
    reference: list[ReferenceNote], detected: list[NoteEvent], rate: int, tempo_scale: float = 1.0
) -> list[AlignedNote]:
    if not 0.5 <= tempo_scale <= 2:
        raise ValueError("Tempo scale outside [0.5,2]")
    rows, cols = len(reference), len(detected)
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
