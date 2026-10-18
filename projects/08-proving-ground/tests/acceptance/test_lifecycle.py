from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pp_proving_ground.cli import clean_output, lifecycle, main, prepare_output
from pp_proving_ground.monitoring.drift import drift_report


def test_pg01_pg04_end_to_end_demo_and_owned_cleanup(tmp_path: Path):
    output = tmp_path / "demo"
    report = lifecycle(output, 5000, 12, 1729)
    assert report["status"] == "passed"
    assert report["correctness_checks"]["prior_rejected"]
    assert report["correctness_checks"]["corruption_refused"]
    assert report["correctness_checks"]["offline_serving_parity_atol_1e-12"]
    assert len(report["metrics"]["inference_seconds"]) == 5
    card = json.loads((output / "model-card.json").read_text())
    assert card["evaluation_question"].startswith("Forecast")
    assert any(not decision["accepted"] for decision in card["decisions"])
    assert card["gate_policy_digest"]
    clean_output(output)
    assert not output.exists()


def test_pg08_drift_schema_and_missingness_are_descriptive():
    rng = np.random.default_rng(3)
    baseline = rng.normal(size=(1000, 4))
    incoming = rng.normal(size=(1000, 4))
    incoming[:, 0] += 2
    incoming[:200, 1] = np.nan
    names = tuple(f"sensor_{i}" for i in range(4))
    report = drift_report(baseline, incoming, names, names)
    assert report["features"][0]["standardized_mean_shift"] > 1.8
    assert report["features"][0]["psi"] > 1
    assert report["features"][1]["incoming_missing_rate"] == 0.2
    assert "accuracy requires" in report["interpretation"]
    assert drift_report(baseline, incoming, names, names[::-1])["schema_failures"]
    assert drift_report(baseline, incoming[:, :3], names, names[:3])["schema_failures"]


def test_safe_demo_paths_and_cleanup_refuses_user_files(tmp_path):
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    (unowned / "precious.txt").write_text("keep")
    with pytest.raises(ValueError):
        prepare_output(unowned)
    with pytest.raises(ValueError):
        clean_output(unowned)
    assert (unowned / "precious.txt").read_text() == "keep"
    owned = prepare_output(tmp_path / "owned")
    (owned / "user.txt").write_text("keep")
    with pytest.raises(ValueError):
        clean_output(owned)
    link = tmp_path / "link"
    link.symlink_to(owned, target_is_directory=True)
    with pytest.raises(ValueError):
        clean_output(link)
    assert main(["clean-demo", "--output", str(unowned)]) == 2


def test_public_staged_cli_generate_train_evaluate_promote_modelcard(tmp_path, capsys):
    output = tmp_path / "staged"
    assert main(["generate", "--output", str(output), "--seed", "1729"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["dataset_digest"]
    assert main(["train", "--output", str(output), "--estimator", "logistic"]) == 0
    trained = json.loads(capsys.readouterr().out)
    version = str(trained["model_version"])
    assert main(["evaluate", "--output", str(output), "--version", version, "--role", "test"]) == 2
    assert "previously promoted" in capsys.readouterr().err
    assert (
        main(
            ["promote", "--output", str(output), "--version", version, "--expected-generation", "0"]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["evaluate", "--output", str(output), "--version", version, "--role", "test"]) == 0
    assert json.loads(capsys.readouterr().out)["role"] == "test"
    assert main(["model-card", "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["deployment"]["model_version"] == int(version)


def test_pg01_retrain_seeded_models_reproduces_heldout_predictions(data, split):
    from pp_proving_ground.training.pipeline import fit, predict

    test = data.features[list(split.test)]
    for estimator in ["prior", "logistic", "tree"]:
        first = fit(data, split, estimator, 1729)
        second = fit(data, split, estimator, 1729)
        np.testing.assert_allclose(
            predict(first.pipeline, test), predict(second.pipeline, test), rtol=0, atol=1e-12
        )


def test_descriptive_monitoring_rejects_invalid_shape_infinite_and_empty():
    names = ("a", "b")
    reference = np.ones((20, 2))
    with pytest.raises(ValueError):
        drift_report(reference[0], reference, names, names)
    assert drift_report(reference, np.full((20, 2), np.inf), names, names)["schema_failures"]
    assert drift_report(reference, np.empty((0, 2)), names, names)["schema_failures"]
    report = drift_report(np.full((20, 2), np.nan), reference, names, names)
    assert report["features"][0]["standardized_mean_shift"] is None
    assert report["features"][0]["psi"] is None
