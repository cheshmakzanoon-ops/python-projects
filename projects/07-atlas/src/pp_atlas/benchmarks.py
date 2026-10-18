"""Deterministic scale workload; quality evaluation is deliberately separate."""

import hashlib
import json
import random
import resource
import statistics
import time
from dataclasses import asdict
from pathlib import Path

from pp_atlas import Document, Engine, Principal
from pp_atlas.provenance import provenance


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[min(len(values) - 1, int(len(values) * fraction))]


def run_benchmark(project: Path, output: Path, profile: str, seed: int) -> dict[str, object]:
    count, tokens, query_count = (200, 80, 30) if profile == "ci" else (100_000, 400, 2_000)
    source = provenance(project)
    randomizer = random.Random(seed)
    engine = Engine(output / "state")
    started = time.perf_counter()
    batch: list[Document] = []
    token_total = 0
    for i in range(count):
        topic = i % 100
        # 50% shared terms, 40% topic-selective terms, 10% rare identities.
        words = [f"topic{topic}"]
        words.extend(f"common{randomizer.randrange(20)}" for _ in range(tokens // 2 - 1))
        words.extend(
            f"domain{topic}term{randomizer.randrange(16)}" for _ in range(tokens * 4 // 10)
        )
        words.extend(f"rare{randomizer.randrange(count)}" for _ in range(tokens - len(words)))
        token_total += len(words)
        batch.append(
            Document(
                f"d{i:07d}",
                f"Generated technical document {i}",
                " ".join(words),
                frozenset({f"group:g{i % 10}"}),
                {"type": "generated", "tag": str(topic)},
            )
        )
        if len(batch) == 1000 or i == count - 1:
            engine.upsert_many("scale", batch)
            batch.clear()
    index_seconds = time.perf_counter() - started
    engine.set_groups("scale", "reader", ["g0"])
    restricted = Principal("scale", "reader")
    engine.set_groups("scale", "all", [f"g{i}" for i in range(10)])
    full = Principal("scale", "all")
    queries = [
        f"topic{(i % 10) * 10}"
        if i % 3 == 0
        else f"common{i % 20}"
        if i % 3 == 1
        else f"rare{randomizer.randrange(count)}"
        for i in range(query_count)
    ]
    started = time.perf_counter()
    cold_engine = Engine(output / "state")
    cold_result = cold_engine.search(restricted, queries[0])
    cold_ms = (time.perf_counter() - started) * 1000
    # Warm index but distinct search-cache contents for reproducible query timing.
    cold_engine.search(restricted, queries[0])
    measurements: list[float] = []
    authorization: list[float] = []
    visibility_cost: list[float] = []
    correctness = True
    for _ in range(5):
        for query in queries:
            start = time.perf_counter()
            result = cold_engine.search(restricted, query)
            measurements.append((time.perf_counter() - start) * 1000)
            correctness = correctness and all(int(h.id[1:]) % 10 == 0 for h in result.hits)
        # Measure authorization + visible-statistics cost under an alternate principal.
        for who in [restricted, full]:
            start = time.perf_counter()
            cold_engine.search(who, "common0", limit=10)
            authorization.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            cold_engine.authorized_ids(who)
            visibility_cost.append((time.perf_counter() - start) * 1000)
    disk_bytes = sum(p.stat().st_size for p in (output / "state").rglob("*") if p.is_file())
    after = provenance(project)
    stable = (
        source["source_content_sha256"] == after["source_content_sha256"]
        and source["root_contract_sha256"] == after["root_contract_sha256"]
    )
    dataset = {
        "generator": "atlas-scale-v1",
        "seed": seed,
        "documents": count,
        "tokens_per_document": tokens,
        "queries": query_count,
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "project": "atlas",
        **source,
        "seed": seed,
        "dataset_id": hashlib.sha256(json.dumps(dataset, sort_keys=True).encode()).hexdigest(),
        "profile": profile,
        "parameters": {
            **dataset,
            "actual_tokens": token_total,
            "term_distribution": "50% common20,40% topic100x16,10% rareN;queries thirds topic/common/rare",
            "acl_distribution": "10 disjoint groups; measured reader sees group0",
            "processes": 1,
            "durability": "fsync segment+directory;SQLite WAL synchronous FULL",
            "cache": "cold load once; warm index+128-entry result LRU",
        },
        "warmup_runs": 1,
        "measurement_runs": 5,
        "metrics": {
            "index_seconds": index_seconds,
            "documents_per_second": count / index_seconds,
            "disk_bytes": disk_bytes,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "cold_query_ms": cold_ms,
            "warm_p50_ms": statistics.median(measurements),
            "warm_p95_ms": percentile(measurements, 0.95),
            "warm_p99_ms": percentile(measurements, 0.99),
            "warm_queries_per_second": len(measurements) / (sum(measurements) / 1000),
            "authorization_plus_search_p50_ms": statistics.median(authorization),
            "authorization_snapshot_p50_ms": statistics.median(visibility_cost),
        },
        "correctness_checks": {
            "authorization": correctness,
            "cold_query_visible_count": cold_result.visible_documents == count // 10,
            "source_unchanged": stable,
        },
        "sample_hit": asdict(cold_result.hits[0]) if cold_result.hits else None,
        "status": "passed" if correctness and stable else "failed",
    }
    return report
