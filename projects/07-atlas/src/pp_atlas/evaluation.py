"""Graded, pooled retrieval evaluation with per-query failure reports."""

import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from pp_atlas import Document, Engine, Principal


@dataclass(frozen=True)
class Judgment:
    id: str
    query: str
    intent: str
    split: str
    grades: dict[str, int]


class _InputDocument(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    title: str
    text: str
    acl: list[str]
    metadata: dict[str, str]


class _Corpus(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    schema_version: Literal[1]
    provenance: str = "caller supplied"
    documents: list[_InputDocument] = Field(max_length=100_000)


def read_bounded(path: Path, maximum: int = 20_000_000) -> str:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("input exceeds 20MB")
    return raw.decode("utf-8")


def load_corpus(path: Path) -> list[Document]:
    payload = _Corpus.model_validate_json(read_bounded(path))
    return [
        Document(d.id, d.title, d.text, frozenset(d.acl), d.metadata) for d in payload.documents
    ]


def load_judgments(path: Path) -> list[Judgment]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Judgment(q["id"], q["query"], q["intent"], q["split"], q["grades"])
        for q in payload["queries"]
    ]


def metrics(ranked: Sequence[str], grades: dict[str, int], k: int = 10) -> dict[str, float]:
    """Unjudged=0, positive grades relevant; recall denominator is judged pool."""
    relevant = {ident for ident, grade in grades.items() if grade > 0}
    ideal = sorted(grades.values(), reverse=True)[:k]
    ideal_dcg = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(ideal))
    actual_dcg = sum(
        (2 ** grades.get(ident, 0) - 1) / math.log2(i + 2) for i, ident in enumerate(ranked[:k])
    )
    reciprocal = next((1 / (i + 1) for i, ident in enumerate(ranked) if ident in relevant), 0.0)
    return {
        "ndcg_at_10": actual_dcg / ideal_dcg if ideal_dcg else 0.0,
        "mrr": reciprocal,
        "pooled_recall_at_10": len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0,
    }


def evaluate(
    engine: Engine, principal: Principal, judgments: Sequence[Judgment], *, baseline: bool = False
) -> dict[str, object]:
    per_query: list[dict[str, object]] = []
    for judgment in judgments:
        query = judgment.query.replace('"', "") if baseline else judgment.query
        result = engine.search(principal, query)
        ranked = [hit.id for hit in result.hits]
        scores = metrics(ranked, judgment.grades)
        per_query.append(
            {
                **asdict(judgment),
                "executed_query": query,
                "ranked": ranked,
                "metrics": scores,
                "unjudged_retrieved": [d for d in ranked if d not in judgment.grades],
                "ranking_failure": scores["ndcg_at_10"] < 0.999999,
            }
        )
    aggregates: dict[str, dict[str, float]] = {}
    for split in ["development", "heldout"]:
        rows = [cast(dict[str, float], q["metrics"]) for q in per_query if q["split"] == split]
        aggregates[split] = {
            key: sum(row[key] for row in rows) / len(rows) if rows else 0.0
            for key in ["ndcg_at_10", "mrr", "pooled_recall_at_10"]
        }
    return {
        "schema_version": 1,
        "mode": "bag_of_words_baseline" if baseline else "phrase_constraints",
        "judgments": "graded0..3; unjudged=0; recall over authored relevant pool",
        "query_count": len(judgments),
        "aggregates": aggregates,
        "per_query": per_query,
    }
