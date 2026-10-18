import json
import math
from pathlib import Path

import pytest

from pp_atlas import Engine, Principal
from pp_atlas.cli import MARKER, clean_output, main
from pp_atlas.evaluation import evaluate, load_corpus, load_judgments, metrics


def test_evaluation_metrics_independent_arithmetic():
    actual = metrics(["irrelevant", "b", "a"], {"a": 3, "b": 1})
    expected = (1 / math.log2(3) + 7 / math.log2(4)) / (7 + 1 / math.log2(3))
    assert actual == pytest.approx({"ndcg_at_10": expected, "mrr": 0.5, "pooled_recall_at_10": 1})
    assert metrics([], {}) == {"ndcg_at_10": 0, "mrr": 0, "pooled_recall_at_10": 0}


def test_at08_frozen_quality_corpus_and_development_improvement(tmp_path):
    examples = Path(__file__).parents[2] / "examples"
    documents = load_corpus(examples / "quality_corpus.json")
    judgments = load_judgments(examples / "quality_judgments.json")
    assert len(documents) >= 250 and len(judgments) >= 60
    assert sum(q.split == "development" for q in judgments) == 30
    assert sum(q.split == "heldout" for q in judgments) == 30
    assert len({q.id for q in judgments}) == len(judgments)
    engine = Engine(tmp_path)
    engine.upsert_many("quality", documents)
    principal = Principal("quality", "public")
    baseline = evaluate(
        engine, principal, [q for q in judgments if q.split == "development"], baseline=True
    )
    improved = evaluate(engine, principal, [q for q in judgments if q.split == "development"])
    assert (
        improved["aggregates"]["development"]["ndcg_at_10"]
        > baseline["aggregates"]["development"]["ndcg_at_10"]
    )
    assert any(row["ranking_failure"] for row in baseline["per_query"])
    # Held-out results are reported, never used for threshold selection/tuning.
    heldout = evaluate(engine, principal, [q for q in judgments if q.split == "heldout"])
    assert heldout["query_count"] == 30


def test_cli_demo_cleanup_and_unowned_file_safety(tmp_path, capsys):
    output = tmp_path / "demo"
    assert main(["demo", "--output", str(output), "--seed", "1729"]) == 0
    report = json.loads((output / "demo.json").read_text())
    assert report["status"] == "passed"
    assert main(["demo", "--output", str(output)]) == 2
    (output / "user.txt").write_text("preserve")
    assert main(["clean-demo", "--output", str(output)]) == 2
    assert (output / "user.txt").read_text() == "preserve"
    (output / "user.txt").unlink()
    assert main(["clean-demo", "--output", str(output)]) == 0
    assert not output.exists()
    clean_output(output)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "notes").write_text("user")
    assert main(["demo", "--output", str(foreign)]) == 2
    assert (foreign / "notes").read_text() == "user"
    link = tmp_path / "link"
    link.symlink_to(foreign, target_is_directory=True)
    assert main(["demo", "--output", str(link)]) == 2
    assert main(["demo", "--output", "/"]) == 2
    assert not (foreign / MARKER).exists()


def test_cli_ingest_search_acl_revision_delete_and_evaluate(tmp_path, capsys):
    examples = Path(__file__).parents[2] / "examples"
    root = tmp_path / "index"
    base = ["--root", str(root), "--tenant", "t"]
    assert main(["ingest", *base, "--input", str(examples / "quality_corpus.json")]) == 0
    assert main(["search", *base, "--subject", "reader", "wal recovery"]) == 0
    assert main(["fetch", *base, "--subject", "reader", "topic-00-runbook"]) == 0
    assert main(["acl", *base, "topic-00-runbook", "--allow", "group:ops"]) == 0
    assert main(["groups", *base, "--subject", "reader", "--group", "ops"]) == 0
    assert main(["inspect", *base]) == 0
    assert main(["merge", *base]) == 0
    assert main(["delete", *base, "topic-00-runbook"]) == 0
    assert main(["fetch", *base, "--subject", "reader", "topic-00-runbook"]) == 2
    assert (
        main(
            [
                "evaluate",
                "--root",
                str(tmp_path / "quality"),
                "--corpus",
                str(examples / "quality_corpus.json"),
                "--judgments",
                str(examples / "quality_judgments.json"),
                "--output",
                str(tmp_path / "evaluation.json"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "evaluate",
                "--root",
                str(tmp_path / "quality"),
                "--corpus",
                str(examples / "quality_corpus.json"),
                "--judgments",
                str(examples / "quality_judgments.json"),
                "--output",
                str(tmp_path / "evaluation.json"),
            ]
        )
        == 2
    )


def test_ci_benchmark_public_command(tmp_path, capsys):
    output = tmp_path / "benchmark"
    assert main(["benchmark", "--profile", "ci", "--output", str(output), "--seed", "1729"]) == 0
    report = json.loads((output / "benchmark.json").read_text())
    assert report["status"] == "passed"
    assert report["parameters"]["documents"] == 200
    assert report["parameters"]["queries"] == 30
    assert report["measurement_runs"] == 5
    assert all(report["correctness_checks"].values())
    assert report["metrics"]["index_seconds"] > 0
    assert report["metrics"]["disk_bytes"] > 0
