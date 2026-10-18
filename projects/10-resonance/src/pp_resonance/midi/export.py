"""Deterministic monophonic MIDI, plus an independent standard-MIDI byte checker."""

import struct
from pathlib import Path

import mido

from pp_resonance.model import AudioSpec, NoteEvent


def export(path: Path, notes: list[NoteEvent], rate: int, tempo: int = 500000) -> None:
    AudioSpec(rate)
    if not 0 < tempo <= 0xFFFFFF:
        raise ValueError("MIDI tempo must fit its positive 24-bit field")
    midi = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    events = []
    last_end = 0
    for note in sorted(notes, key=lambda n: (n.start, n.id)):
        if (
            not isinstance(note.start, int)
            or not isinstance(note.end, int)
            or not isinstance(note.midi, int)
            or isinstance(note.midi, bool)
            or note.start < last_end
            or note.end <= note.start
            or not 0 <= note.midi <= 127
        ):
            raise ValueError("MIDI baseline requires valid, ordered monophonic note intervals")
        last_end = note.end
        for sample, kind, velocity in ((note.start, "note_on", 90), (note.end, "note_off", 0)):
            tick = round(sample / rate * 1_000_000 / tempo * 480)
            events.append((tick, 0 if kind == "note_off" else 1, note.midi, kind, velocity))
        if events[-1][0] <= events[-2][0]:
            raise ValueError(
                "Note interval quantizes to less than one MIDI tick; increase duration or resolution"
            )
    previous = 0
    for tick, _, pitch, kind, velocity in sorted(events):
        track.append(mido.Message(kind, note=pitch, velocity=velocity, time=tick - previous))
        previous = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(path)


def check_bytes(path: Path) -> list[tuple[int, int, int]]:
    """Parse exported type-0 SMF without mido, verifying tempo and note lifecycle."""
    raw = path.read_bytes()
    if len(raw) < 22 or raw[:4] != b"MThd" or struct.unpack(">IHHH", raw[4:14]) != (6, 0, 1, 480):
        raise ValueError("Unexpected MIDI header")
    if raw[14:18] != b"MTrk" or int.from_bytes(raw[18:22], "big") != len(raw) - 22:
        raise ValueError("Invalid MIDI track length")
    position, tick, tempo_seen, ended = 22, 0, False, False
    active: dict[int, int] = {}
    notes = []

    def variable() -> int:
        nonlocal position
        value = 0
        for _ in range(4):
            if position >= len(raw):
                raise ValueError("Truncated MIDI integer")
            byte = raw[position]
            position += 1
            value = (value << 7) | (byte & 127)
            if byte < 128:
                return value
        raise ValueError("Invalid variable-length MIDI integer")

    while position < len(raw):
        tick += variable()
        if position >= len(raw):
            raise ValueError("Truncated MIDI status")
        status = raw[position]
        position += 1
        if status == 255:
            if position >= len(raw):
                raise ValueError("Truncated MIDI meta event")
            kind = raw[position]
            position += 1
            length = variable()
            if position + length > len(raw):
                raise ValueError("Truncated MIDI payload")
            payload = raw[position : position + length]
            position += length
            if kind == 81:
                if len(payload) != 3 or int.from_bytes(payload, "big") <= 0:
                    raise ValueError("Require a positive explicit 24-bit MIDI tempo")
                tempo_seen = True
            if kind == 47:
                ended = True
        elif status in (128, 144):
            if position + 2 > len(raw):
                raise ValueError("Truncated MIDI note event")
            pitch, velocity = raw[position : position + 2]
            position += 2
            if status == 144 and velocity:
                if pitch in active:
                    raise ValueError("Duplicate note-on")
                active[pitch] = tick
            else:
                if pitch not in active:
                    raise ValueError("Unpaired note-off")
                notes.append((pitch, active.pop(pitch), tick))
        else:
            raise ValueError("Unsupported status in generated MIDI")
    if active or not tempo_seen or not ended:
        raise ValueError("Incomplete MIDI lifecycle")
    return notes
