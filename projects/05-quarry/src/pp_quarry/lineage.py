"""Public lineage access delegates to the authoritative version registry."""

from typing import Any

from pp_quarry.execution.engine import Lakehouse


def explain(lake: Lakehouse, namespace: str, key: str) -> dict[str, Any]:
    return lake.lineage(namespace, key)
