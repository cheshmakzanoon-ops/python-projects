"""Bounded deterministic numerical/alignment workload; compare imported snapshots.

Run with this project's locked interpreter. PYTHONPATH may select an exported
historical package without changing this workload or its independently scored grid.
"""

import argparse
import hashlib
import inspect
import json
import math
import platform
import statistics
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

import pp_resonance
from pp_resonance.alignment.dynamic import align
from pp_resonance.analysis import analyze_chunks
from pp_resonance.metrics.evaluate import trajectory_metrics
from pp_resonance.model import AnalysisConfig, NoteEvent, OnsetEvent, PitchFrame, ReferenceNote
from pp_resonance.notes.decode import decode
from pp_resonance.onsets.detect import detect
from pp_resonance.pitch.difference import estimate, normalize
from pp_resonance.streaming.framing import Framer
from pp_resonance.synthesis.tones import Tone, challenge, chunks


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer")
    return number


def digest_code(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def imported_modules(package: Path) -> dict[str, str]:
    paths = {
        name: str(Path(module.__file__).resolve())
        for name, module in sorted(sys.modules.items())
        if (name == "pp_resonance" or name.startswith("pp_resonance."))
        and getattr(module, "__file__", None) is not None
    }
    if any(not Path(path).is_relative_to(package) for path in paths.values()):
        raise RuntimeError("Imported Resonance modules must come from one package snapshot")
    return paths


def semantic_witnesses() -> dict[str, object]:
    rate = 48000
    values = np.array([0, 2, 5, 1, 3, 0.1], dtype=np.float64)
    prefix, extended = [0.0] * 40, [0.0] * 80
    prefix[10], extended[10], extended[60] = 1.0, 1.0, 100.0
    signal = np.sin(2 * np.pi * 440 * np.arange(2048) / rate)
    tiny = estimate(signal * 1e-15, rate, 0, AnalysisConfig(silence_rms=1e-18))
    framer = Framer()
    samples = np.ones(4096)
    batch = framer.feed(samples)
    immediate = framer.received
    samples[:] = 0
    first = next(batch)
    batch.close()
    remaining = list(framer.feed(np.empty(0), final=True))
    frames = [
        PitchFrame(s, s + 1024, 440, 1, 0.2, "voiced")
        for s in range(0, 48000, 256)
        if 0.2 <= (s + 1024) / rate <= 0.45
    ]
    kwargs = (
        {"sample_count": 48000}
        if "sample_count" in inspect.signature(trajectory_metrics).parameters
        else {}
    )
    complete = trajectory_metrics(frames, [Tone(69, 0.1, 0.4)], rate, **kwargs)
    omitted = trajectory_metrics(frames[:1], [Tone(69, 0.1, 0.4)], rate, **kwargs)
    note_frames = [PitchFrame(s, s + 1024, 440, 1, 0.2, "voiced") for s in range(4096, 24000, 256)]
    clean = decode(note_frames, [], rate, 256, 30000)
    weak = decode(note_frames, [OnsetEvent(6000, 0.1)], rate, 256, 30000)
    return {
        "cmnd_scale_invariant": bool(np.allclose(normalize(values), normalize(values * 1e-30))),
        "tiny_above_configured_silence_is_voiced": tiny.frequency is not None,
        "onsets_before_future_peak": [
            o.sample for o in detect(prefix, list(range(0, 40 * 256, 256)), rate, 2048)
        ],
        "onsets_after_future_peak": [
            o.sample for o in detect(extended, list(range(0, 80 * 256, 256)), rate, 2048)
        ],
        "input_samples_accepted_before_iteration": immediate,
        "first_frame_preserves_caller_input": bool(np.all(first[1] == 1)),
        "duplicate_frame_starts_after_close": len({first[0], *(s for s, _ in remaining)})
        != 1 + len(remaining),
        "full_output_eligible_frames": complete["eligible_voiced_frames"],
        "one_frame_output_eligible_frames": omitted["eligible_voiced_frames"],
        "one_frame_output_recall": omitted["voicing_recall"],
        "weak_onsets_leave_note_boundaries_unchanged": clean == weak,
    }


def run(repetitions: int = 5) -> dict[str, object]:
    package_root = Path(pp_resonance.__file__).resolve().parent
    package_hash = digest_code(package_root)
    workload_path = Path(__file__).resolve()
    workload_hash = hashlib.sha256(workload_path.read_bytes()).hexdigest()
    rate = 48000
    alignment_results = []
    for count in (100, 300, 600):
        reference = [
            ReferenceNote(f"r{i}", 50 + i % 20, i * 24000, i * 24000 + 18000) for i in range(count)
        ]
        detected = [
            NoteEvent(
                f"n{i}", r.midi, r.start + (i % 5) * 173, r.end + (i % 5) * 173, 440.0, 0.95, 8.0
            )
            for i, r in enumerate(reference)
            if i % 13 != 7
        ]
        parameters = json.dumps(
            {
                "reference": [asdict(r) for r in reference],
                "detected": [asdict(n) for n in detected],
            },
            sort_keys=True,
        )
        timings = []
        for _ in range(repetitions):
            before = time.perf_counter()
            result = align(reference, detected, rate)
            timings.append(time.perf_counter() - before)
        assert len(result) == count
        assert sum(r.detected_id is None for r in result) == count - len(detected)
        assert all(r.reference_id is not None for r in result)
        mapping = [(r.reference_id, r.detected_id, r.timing_samples, r.cents) for r in result]
        alignment_results.append(
            {
                "reference_notes": count,
                "detected_notes": len(detected),
                "cells": (count + 1) * (len(detected) + 1),
                "dataset_sha256": hashlib.sha256(parameters.encode()).hexdigest(),
                "mapping_sha256": hashlib.sha256(json.dumps(mapping).encode()).hexdigest(),
                "seconds": timings,
                "measurement_runs": len(timings),
                "median_seconds": statistics.median(timings),
                "cost": sum(r.cost for r in result),
            }
        )

    duration, block, seed = 12.0, 8192, 1729
    tones = [
        replace(t, amplitude=0.6 if i % 2 else 0.06) for i, t in enumerate(challenge(duration))
    ]
    parameters = {
        "tones": [asdict(t) for t in tones],
        "rate": rate,
        "duration": duration,
        "block": block,
        "seed": seed,
        "noise": 0.0005,
    }
    audio_timings = []
    for _ in range(repetitions):
        before = time.perf_counter()
        report = analyze_chunks(chunks(tones, rate, duration, block, 0.0005, seed), rate)
        audio_timings.append(time.perf_counter() - before)
    # Independent fixed input grid; never derive eligibility from returned frames.
    by_start = {frame.start: frame for frame in report.pitches}
    errors, eligible, missed = [], 0, 0
    for start in range(0, round(duration * rate), 256):
        center = (start + 1024) / rate
        tone = next(
            (t for t in tones if t.onset + 0.10 <= center <= t.onset + t.duration - 0.05), None
        )
        if tone is None:
            continue
        eligible += 1
        frame = by_start.get(start)
        if frame is None or frame.frequency is None:
            missed += 1
            continue
        relative = center - tone.onset
        depth = math.log(2) / 1200
        expected = (
            440
            * 2 ** ((tone.midi - 69) / 12)
            * (
                1
                + tone.vibrato_cents * depth * math.sin(2 * math.pi * 5 * relative)
                + tone.bend_cents * depth * relative / tone.duration
            )
        )
        errors.append(abs(1200 * math.log2(frame.frequency / expected)))
    witnesses = semantic_witnesses()
    if (
        digest_code(package_root) != package_hash
        or hashlib.sha256(workload_path.read_bytes()).hexdigest() != workload_hash
    ):
        raise RuntimeError("Package or workload source changed during measurement")
    return {
        "workload": "resonance-core-review-v2",
        "python": platform.python_version(),
        "workload_path": str(workload_path),
        "workload_sha256": workload_hash,
        "package_path": str(package_root),
        "package_python_sha256": package_hash,
        "package_inputs": [
            path.relative_to(package_root).as_posix() for path in sorted(package_root.rglob("*.py"))
        ],
        "imported_modules": imported_modules(package_root),
        "repetitions": repetitions,
        "inputs_unchanged": True,
        "limits": {
            "alignment_max_cells": 4_000_000,
            "audio_seconds": duration,
            "alignment_repeats": repetitions,
            "audio_repeats": repetitions,
            "threads": 1,
            "exclusive_host": False,
        },
        "alignment": alignment_results,
        "semantic_witnesses": witnesses,
        "dynamic_synthetic_phrase": {
            "dataset_sha256": hashlib.sha256(
                json.dumps(parameters, sort_keys=True).encode()
            ).hexdigest(),
            "parameters": parameters,
            "seconds": audio_timings,
            "measurement_runs": len(audio_timings),
            "median_seconds": statistics.median(audio_timings),
            "eligible_frames": eligible,
            "voiced_misses": missed,
            "within_10_cents_all_eligible": sum(e <= 10 for e in errors) / eligible,
            "truth_notes": len(tones),
            "detected_notes": len(report.notes),
            "detected_onsets": len(report.onsets),
            "peak_input_buffer_samples": report.peak_buffer_samples,
        },
        "limits_of_inference": [
            "Authored synthetic signals; no real-recording or polyphonic accuracy claim.",
            "Shared-host microtimings describe these inputs, not an exclusive standard benchmark.",
            "Package digest covers Python code; workload/dataset hashes fix the comparison inputs.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=positive_int, default=5)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.repetitions), indent=2, allow_nan=False) + "\n")
