"""Deliberately batch-oriented independent trace oracle (no runtime imports)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def reconcile(
    raw: list[dict[str, Any]],
    *,
    inputs: tuple[str, ...],
    size: int,
    slide: int,
    lateness: int,
    interval: int,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    clocks = dict.fromkeys(inputs, -(2**63))
    inactive: set[str] = set()
    watermark = -(2**63)
    dispositions = []
    values: dict[str, list[int]] = defaultdict(list)
    accepted: dict[str, list[tuple[dict[str, Any], int]]] = defaultdict(list)
    result: dict[str, dict[str, object]] = {}
    for row in raw:
        identity = json.dumps([row["source_id"], row["partition"]], separators=(",", ":"))
        kind = row["kind"]
        timestamp = row["event_time"]
        if kind == "event":
            disposition = (
                "rejected-late"
                if timestamp + lateness < watermark
                else "accepted-late"
                if timestamp < watermark
                else "on-time"
            )
            dispositions.append(disposition)
            if disposition == "rejected-late":
                continue
            if row["stream"] == "reading":
                for operator, step in [("tumbling", size), ("sliding", slide)]:
                    # Enumerate boundary indices rather than using runtime assignment.
                    for index in range((timestamp - size) // step + 1, timestamp // step + 1):
                        start = index * step
                        key = json.dumps([row["key"], start, start + size], separators=(",", ":"))
                        values[operator + ":" + key].append(row["value"])
            # Expire the key-local candidate set independently from runtime heaps.
            accepted[row["key"]] = [
                (previous, admitted_watermark)
                for previous, admitted_watermark in accepted[row["key"]]
                if previous["event_time"] + interval + lateness >= watermark
            ]
            for previous, _ in accepted[row["key"]]:
                if (
                    previous["stream"] != row["stream"]
                    and previous["event_time"] + interval + lateness >= watermark
                    and abs(previous["event_time"] - timestamp) <= interval
                ):
                    left, right = (row, previous) if row["stream"] == "reading" else (previous, row)
                    key = json.dumps(
                        [left["ingress_ordinal"], right["ingress_ordinal"]], separators=(",", ":")
                    )
                    result["interval-join:" + key] = {
                        "key": row["key"],
                        "reading_ordinal": left["ingress_ordinal"],
                        "metadata_ordinal": right["ingress_ordinal"],
                        "value": left["value"],
                        "metadata": right["payload"],
                        "delta_ms": right["event_time"] - left["event_time"],
                    }
            accepted[row["key"]].append((row, watermark))
        else:
            dispositions.append(kind)
            if kind == "idle":
                inactive.add(identity)
            elif kind == "resume":
                inactive.discard(identity)
            elif kind in ("watermark", "end"):
                next_time = 2**63 - 1 if kind == "end" else timestamp
                if next_time < clocks[identity]:
                    raise ValueError("oracle observed regressing clock")
                clocks[identity] = next_time
            active = [clock for source, clock in clocks.items() if source not in inactive]
            if active:
                watermark = max(watermark, min(active))
    for identity, samples in values.items():
        _, logical = identity.split(":", 1)
        key, start, end = json.loads(logical)
        if end <= watermark:
            result[identity] = {
                "key": key,
                "start": start,
                "end": end,
                "count": len(samples),
                "sum": sum(samples),
                "min": min(samples),
                "max": max(samples),
                "average": sum(samples) / len(samples),
            }
    return dispositions, result
