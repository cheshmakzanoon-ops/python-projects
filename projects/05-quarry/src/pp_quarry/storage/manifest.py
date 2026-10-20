"""Structural format checks shared by publication, readers and reclamation."""

from __future__ import annotations

import re
from typing import Any

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_NODES = {
    "normalized": ("normalize", []),
    "facts": ("facts", ["normalized"]),
    "daily": ("daily", ["facts"]),
}


def validate_manifest(value: object, buckets: int) -> dict[str, Any]:
    """Reject incomplete catalogs before files can be classified as orphans.

    Even empty datasets publish one file for every node in every bucket. An
    empty or shortened partition map is corruption, not an empty snapshot.
    Content verification remains separate so recovery need not hash all files.
    """
    if (
        not isinstance(value, dict)
        or type(value.get("format_version")) is not int
        or value["format_version"] != 1
    ):
        raise ValueError("unsupported or invalid manifest format")
    partitions = value.get("partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        str(partition) for partition in range(buckets)
    }:
        raise ValueError("manifest must contain every configured bucket exactly once")
    for partition, nodes in partitions.items():
        if not isinstance(nodes, dict) or set(nodes) != _NODES.keys():
            raise ValueError("manifest bucket must contain normalized, facts and daily nodes")
        for name, (transform, parents) in _NODES.items():
            entry = nodes[name]
            if not isinstance(entry, dict):
                raise ValueError("manifest node must be an object")
            path = entry.get("path")
            if (
                not isinstance(path, str)
                or re.fullmatch(rf"data/{name}-{partition}-[0-9a-f]{{32}}\.parquet", path) is None
            ):
                raise ValueError("manifest path must identify its owned node and bucket")
            if (
                entry.get("transform") != transform
                or entry.get("parents") != parents
                or not isinstance(entry.get("schema"), str)
                or not entry["schema"]
            ):
                raise ValueError("invalid manifest node schema or dependencies")
            if any(
                type(entry.get(field)) is not int or entry[field] < 0 for field in ("bytes", "rows")
            ):
                raise ValueError("manifest sizes and row counts must be nonnegative integers")
            for field in ("sha256", "fingerprint"):
                digest = entry.get(field)
                if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
                    raise ValueError("invalid manifest content or semantic digest")
            inputs = entry.get("input_fingerprints")
            if (
                not isinstance(inputs, list)
                or len(inputs) != 1
                or not isinstance(inputs[0], str)
                or _DIGEST.fullmatch(inputs[0]) is None
            ):
                raise ValueError("invalid manifest input fingerprints")
    return value
