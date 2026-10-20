"""Bounded allocation diagnostic; not a throughput or capacity benchmark."""

import argparse
import gc
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from pp_atlas import Document, Engine, Principal
from pp_atlas.provenance import provenance


class CountingEngine(Engine):
    visibility_scans = 0

    def _visible(self, principal, snapshot, query):
        self.visibility_scans += 1
        return super()._visible(principal, snapshot, query)


def measured_search(engine, principal, query):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    result = engine.search(principal, query, limit=10)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {"seconds": elapsed, "peak_python_allocation_bytes": peak}


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    report = {
        "schema_version": 1,
        "diagnostic": "warm-generation uncached top-10 and identical cached query",
        "limitations": "one sample per size; tracemalloc overhead; excludes index load/RSS; not standard-workload evidence",
        "provenance": provenance(project),
        "samples": [],
    }
    terms = tuple(f"term{i}" for i in range(8))
    text = " ".join(terms)
    principal = Principal("t", "reader")
    for count in (1000, 5000):
        with tempfile.TemporaryDirectory(prefix="atlas-query-diagnostic-") as directory:
            engine = CountingEngine(directory)
            engine.upsert_many("t", (Document(f"{i:06}", "Fixture", text) for i in range(count)))
            engine.inspect("t")
            result, uncached = measured_search(engine, principal, text)
            scans_before = engine.visibility_scans
            cached, cache_hit = measured_search(engine, principal, text)
            assert result == cached
            assert result.total == count
            assert [hit.id for hit in result.hits] == [f"{i:06}" for i in range(10)]
            assert all(len(hit.explanation) == 8 for hit in result.hits)
            report["samples"].append(
                {
                    "documents": count,
                    "terms_per_document_and_query": 8,
                    "limit": 10,
                    "uncached": uncached,
                    "cache_hit": cache_hit,
                    "cache_hit_visibility_scans": engine.visibility_scans - scans_before,
                    "exact_total_ids_explanations_and_cache_equality": True,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    run()
