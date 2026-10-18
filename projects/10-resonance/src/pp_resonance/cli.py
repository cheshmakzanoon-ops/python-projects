"""User-facing commands run the same original core as the numerical tests."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import soundfile as sf

from pp_resonance.alignment.dynamic import align, load_score
from pp_resonance.analysis import analyze, analyze_chunks
from pp_resonance.audio_io.pcm import blocks, preview, write
from pp_resonance.benchmark import benchmark
from pp_resonance.metrics.evaluate import pitch_grid
from pp_resonance.midi.export import check_bytes, export
from pp_resonance.model import NoteEvent, ReferenceNote
from pp_resonance.provenance import metadata
from pp_resonance.reports.render import render, report_json
from pp_resonance.synthesis.tones import clean_plucks
from pp_resonance.synthesis.tones import render as synthesize

OWNER = ".resonance-demo.json"
OWNED = (
    "audio.wav",
    "analysis.json",
    "analysis.html",
    "analysis.png",
    "transcription.mid",
    "reference.json",
    "benchmark.json",
    "pitch-grid.json",
)


def prepare(path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Output must be an absolute directory, not a symlink")
    path = path.resolve()
    if path.exists() and any(path.iterdir()) and not (path / OWNER).is_file():
        raise ValueError("Refusing to overwrite a nonempty directory without Resonance ownership")
    path.mkdir(parents=True, exist_ok=True)
    marker = path / OWNER
    if marker.is_symlink():
        raise ValueError("Refusing ownership marker symlink")
    if marker.exists() and json.loads(marker.read_text()) != {
        "owner": "pp-resonance",
        "version": 1,
    }:
        raise ValueError("Invalid Resonance ownership marker")
    for name in OWNED:
        if (path / name).is_symlink():
            raise ValueError("Refusing output symlink")
    marker.write_text(json.dumps({"owner": "pp-resonance", "version": 1}))
    return path


def clean(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Clean requires an absolute owned directory, not a symlink")
    marker = path / OWNER
    if not marker.is_file() or json.loads(marker.read_text()) != {
        "owner": "pp-resonance",
        "version": 1,
    }:
        raise ValueError("Refusing to clean unowned output")
    for name in OWNED:
        target = path / name
        if target.is_symlink():
            raise ValueError("Refusing to clean symlinked output")
        if target.is_file():
            target.unlink()
    marker.unlink()
    # Preserve unrelated files a user may have added.
    if not any(path.iterdir()):
        path.rmdir()


def save_demo(path: Path, seed: int) -> dict[str, object]:
    rate = 48000
    tones = clean_plucks()
    audio = synthesize(tones, rate, round(4.9 * rate))
    write(path / "audio.wav", audio, rate)
    # Analyze actual encoded PCM, so audio, figure and exported events agree.
    actual, actual_rate = sf.read(path / "audio.wav", dtype="float64")
    report = analyze(np.asarray(actual, dtype=np.float64), int(actual_rate))
    reference = [
        ReferenceNote(f"r{i}", t.midi, round(t.onset * rate), round((t.onset + t.duration) * rate))
        for i, t in enumerate(tones)
    ]
    report.alignment = align(reference, report.notes, rate)
    provenance = metadata(seed, "demo")
    provenance["audio_sha256"] = hashlib.sha256((path / "audio.wav").read_bytes()).hexdigest()
    data = report_json(report, provenance)
    (path / "analysis.json").write_text(json.dumps(data, indent=2, allow_nan=False))
    (path / "reference.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "units": "seconds",
                "tempo_bpm": 120,
                "notes": [
                    {
                        "id": r.id,
                        "midi": r.midi,
                        "onset": r.start / rate,
                        "duration": (r.end - r.start) / rate,
                    }
                    for r in reference
                ],
            },
            indent=2,
        )
    )
    export(path / "transcription.mid", report.notes, rate)
    checked = check_bytes(path / "transcription.mid")
    if len(checked) != len(report.notes):
        raise RuntimeError("Independent MIDI check failed")
    render(
        path / "analysis.html",
        report,
        path / "audio.wav",
        np.asarray(actual, dtype=np.float64),
        reference,
        provenance,
    )
    return {
        "notes": len(report.notes),
        "midi_checked": len(checked),
        "report": str(path / "analysis.html"),
        "diagnostics": report.diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline monophonic guitar analysis; no hosted models"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        "demo",
        "benchmark",
        "clean-demo",
        "synthesize",
        "analyze",
        "align",
        "compare",
        "export",
    ):
        child = sub.add_parser(command)
        child.add_argument("--output", type=Path, required=True)
        child.add_argument("--seed", type=int, default=1729)
        if command == "benchmark":
            child.add_argument("--profile", choices=("ci", "standard"), default="ci")
        if command in ("analyze", "align", "export"):
            child.add_argument("--input", type=Path, required=True)
        if command in ("analyze", "align"):
            child.add_argument("--score", type=Path, required=command == "align")
    args = parser.parse_args()
    try:
        if args.command == "clean-demo":
            clean(args.output)
            print("Removed only Resonance-owned files")
            return
        result: dict[str, object]
        output = prepare(args.output)
        if args.command == "demo":
            result = save_demo(output, args.seed)
        elif args.command == "benchmark":
            result = benchmark(args.profile, args.seed)
            (output / "benchmark.json").write_text(json.dumps(result, indent=2, allow_nan=False))
            if result["status"] != "passed":
                raise RuntimeError("Benchmark correctness checks failed")
        elif args.command == "compare":
            result = dict(pitch_grid(args.seed))
            (output / "pitch-grid.json").write_text(json.dumps(result, indent=2))
        elif args.command == "synthesize":
            tones = clean_plucks()
            write(output / "audio.wav", synthesize(tones, 48000, 235200), 48000)
            result = {
                "audio": str(output / "audio.wav"),
                "ground_truth": [asdict(t) for t in tones],
            }
        elif args.command in ("analyze", "align"):
            spec, chunks = blocks(args.input)
            report = analyze_chunks(chunks, spec.sample_rate)
            reference = load_score(args.score, spec.sample_rate) if args.score else []
            if reference:
                report.alignment = align(reference, report.notes, spec.sample_rate)
            if spec.channels == 2:
                report.diagnostics.append(
                    "stereo: fixed energetic channel chosen from first second"
                )
            provenance = metadata(args.seed, "analysis")
            with args.input.open("rb") as source:
                provenance["audio_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
            clip = preview(args.input)
            if len(clip) < report.sample_count:
                report.diagnostics.append(
                    "Playback and figure show first 30s; JSON/MIDI cover full recording"
                )
            write(output / "audio.wav", clip, spec.sample_rate)
            encoded, _ = sf.read(output / "audio.wav", dtype="float64")
            render(
                output / "analysis.html",
                report,
                output / "audio.wav",
                np.asarray(encoded, dtype=np.float64),
                reference,
                provenance,
            )
            data = report_json(report, provenance)
            (output / "analysis.json").write_text(json.dumps(data, indent=2, allow_nan=False))
            export(output / "transcription.mid", report.notes, spec.sample_rate)
            result = {
                "notes": len(report.notes),
                "analysis": str(output / "analysis.json"),
                "report": str(output / "analysis.html"),
            }

        else:
            data = json.loads(args.input.read_text())
            if data.get("schema_version") != 1:
                raise ValueError("Require analysis schema_version=1")
            notes = [NoteEvent(**n) for n in data["notes"]]
            export(output / "transcription.mid", notes, data["sample_rate"])
            result = {"midi_notes_checked": len(check_bytes(output / "transcription.mid"))}
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"resonance: {error}\n")


if __name__ == "__main__":
    main()
