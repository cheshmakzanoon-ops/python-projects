"""Seeded bounded-input timing and domain evaluation workloads."""

import hashlib
import json
import statistics
import sys
import time
from dataclasses import asdict

from pp_resonance.alignment.dynamic import align
from pp_resonance.analysis import analyze_chunks
from pp_resonance.metrics.evaluate import (
    note_metrics,
    onset_metrics,
    pitch_grid,
    trajectory_metrics,
)
from pp_resonance.model import ReferenceNote
from pp_resonance.provenance import metadata
from pp_resonance.synthesis.tones import challenge, chunks


def benchmark(profile: str, seed: int) -> dict[str, object]:
    duration = 60.0 if profile == "ci" else 600.0
    rate, block = 48000, 8192
    tones = challenge(duration)
    provenance = metadata(seed, profile)
    timings = []
    # Warmup uses the same kernels and state transitions without allocating a whole track.
    analyze_chunks(chunks(tones[:4], rate, 4, block, 0.0005, seed), rate)
    for _ in range(5):
        before = time.perf_counter()
        report = analyze_chunks(chunks(tones, rate, duration, block, 0.0005, seed), rate)
        timings.append(time.perf_counter() - before)
    references = [
        ReferenceNote(f"r{i}", t.midi, round(t.onset * rate), round((t.onset + t.duration) * rate))
        for i, t in enumerate(tones)
    ]
    before_align = time.perf_counter()
    mapping = align(references, report.notes, rate)
    alignment_seconds = time.perf_counter() - before_align
    grid = pitch_grid(seed)
    quality = note_metrics(report.notes, tones, rate)
    matches = [
        item for item in mapping if item.reference_id is not None and item.detected_id is not None
    ]
    limit = block + 2048 - 1
    correctness = {
        "RE-01_fixed_grid": grid["success_ratio"] >= 0.95,
        "bounded_input_buffer": report.peak_buffer_samples <= limit,
        "all_samples_processed": report.sample_count == round(duration * rate),
    }
    after = metadata(seed, profile)
    correctness["source_unchanged"] = (
        after["source_content_sha256"] == provenance["source_content_sha256"]
        and after["root_contract_sha256"] == provenance["root_contract_sha256"]
    )
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes: int | None = peak if sys.platform == "darwin" else peak * 1024
    except ImportError:
        peak_bytes = None
    dataset = json.dumps(
        {
            "tones": [asdict(t) for t in tones],
            "rate": rate,
            "duration": duration,
            "noise_stddev": 0.0005,
            "seed": seed,
        },
        sort_keys=True,
    )
    return {
        **provenance,
        "dataset_id": "authored-challenge-v1:" + hashlib.sha256(dataset.encode()).hexdigest(),
        "parameters": {
            "duration_seconds": duration,
            "sample_rate": rate,
            "block_samples": block,
            "frame_samples": 2048,
            "hop_samples": 256,
            "processes": 1,
            "noise_stddev": 0.0005,
        },
        "warmup_runs": 1,
        "measurement_runs": 5,
        "metrics": {
            "processing_seconds": timings,
            "median_seconds": statistics.median(timings),
            "p95_seconds": 0.2 * sorted(timings)[3] + 0.8 * sorted(timings)[4],
            "real_time_factor": statistics.median(timings) / duration,
            "throughput_audio_seconds_per_second": duration / statistics.median(timings),
            "peak_process_memory_bytes": peak_bytes,
            "peak_input_buffer_samples": report.peak_buffer_samples,
            "fixed_pitch_grid": grid,
            "challenge_trajectory": trajectory_metrics(report.pitches, tones, rate),
            "challenge_notes": quality,
            "challenge_onsets": onset_metrics([o.sample for o in report.onsets], tones, rate),
            "challenge_voiced_frames": sum(p.frequency is not None for p in report.pitches),
            "challenge_total_frames": len(report.pitches),
            "alignment_cost": sum(a.cost for a in mapping),
            "alignment_match_count": len(matches),
            "alignment_missing_count": sum(a.detected_id is None for a in mapping),
            "alignment_extra_count": sum(a.reference_id is None for a in mapping),
            "alignment_wrong_pitch_count": sum(abs(a.cents or 0) > 50 for a in matches),
            "alignment_seconds": alignment_seconds,
        },
        "correctness_checks": correctness,
        "status": "passed" if all(correctness.values()) else "failed",
        "measurement_notes": [
            "Peak RSS is process-wide high-water memory, including warmup and evaluation.",
            "Five warm repetitions; disk I/O and plot rendering excluded.",
            "Input sample buffers bounded; output records grow linearly with duration.",
            "Synthetic challenge metrics are separate from fixed clean acceptance gates.",
        ],
    }
