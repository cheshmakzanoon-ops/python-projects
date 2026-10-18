from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

import pp_proving_ground.serving.service as serving_module
from pp_proving_ground.evaluation.metrics import GatePolicy, evaluate
from pp_proving_ground.registry.sqlite import PromotionRejected, Registry
from pp_proving_ground.serving.api import create_app
from pp_proving_ground.serving.service import ServingProcess, Unavailable
from pp_proving_ground.training.pipeline import fit, predict


def second_candidate(context, data, split):
    trained = fit(data, split, "logistic", parameters={"C": 0.2})
    manifest = context.store.publish(
        trained, "b" * 64, data.identity, split.identity, tuple(f.name for f in data.schema)
    )
    report = evaluate(trained, data, split, manifest.identity, bootstrap_repetitions=5)
    return context.registry.register(manifest.identity, report)


def test_candidate_binding_failure_policy_and_audit(context, data, split):
    report = context.report
    for broken in [
        replace(report, artifact_digest="f" * 64),
        replace(report, dataset_digest="wrong"),
        replace(report, split_digest="wrong"),
    ]:
        with pytest.raises(ValueError, match="bind"):
            context.registry.register(context.manifest.identity, broken)
    with pytest.raises(ValueError, match="immutable"):
        context.registry.register(context.manifest.identity, replace(report, uncertainty={}))
    with pytest.raises(PromotionRejected, match="requested evaluation"):
        context.registry.promote(context.model.version, 0, evaluation_digest="wrong")
    assert context.registry.current().generation == 0
    decision = context.registry.audit()[-1]
    assert not decision["accepted"]
    assert decision["artifact_digest"] == context.manifest.identity
    assert decision["dataset_digest"] == data.identity
    assert decision["split_digest"] == split.identity
    assert decision["policy_digest"] == GatePolicy().identity
    assert decision["evaluation_digest"] == report.identity
    with pytest.raises(ValueError, match="frozen policy"):
        Registry(context.registry.path, context.store, replace(GatePolicy(), minimum_pr_auc=0.01))
    context.registry.promote(context.model.version, 0)
    assert context.registry.audit()[-1]["accepted"]


def test_racing_promotions_have_one_winner(context):
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait(timeout=5)
        try:
            return context.registry.promote(context.model.version, 0).generation
        except PromotionRejected:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes, key=str) == [1, "rejected"]
    assert context.registry.current().generation == 1
    assert len(context.registry.audit()) == 2
    assert sum(d["accepted"] for d in context.registry.audit()) == 1


def test_old_slow_load_cannot_replace_newer(context, data, split):
    second = second_candidate(context, data, split)
    context.registry.promote(context.model.version, 0)
    started, release = threading.Event(), threading.Event()

    def loader(artifact):
        if artifact == context.manifest.identity:
            started.set()
            assert release.wait(10)
        return context.store.load(artifact)

    process = ServingProcess(context.registry, loader)
    with ThreadPoolExecutor(max_workers=1) as pool:
        slow = pool.submit(process.refresh)
        assert started.wait(5)
        context.registry.promote(second.version, 1)
        assert process.refresh()
        release.set()
        assert slow.result(timeout=10) is False
    prediction = process.predict(data.features[:3])
    assert prediction.model_version == second.version
    assert prediction.applied_generation == 2
    assert process.readiness()["ready"]


def test_failed_load_retains_old_snapshot_rollback_new_generation(context, data, split):
    second = second_candidate(context, data, split)
    process = ServingProcess(context.registry)
    with pytest.raises(Unavailable):
        process.predict(data.features[:1])
    assert not process.refresh()
    assert not process.readiness()["ready"]
    context.registry.promote(context.model.version, 0)
    assert process.refresh()
    before = process.predict(data.features[:3])
    context.registry.promote(second.version, 1)
    model_path = context.store.path(second.artifact_digest) / "model.skops"
    model_path.write_bytes(b"corrupt")
    assert not process.refresh()
    after = process.predict(data.features[:3])
    assert before == after
    assert process.readiness()["requested_generation"] == 2
    assert process.readiness()["applied_generation"] == 1
    assert process.readiness()["load_error"] is not None
    assert not process.readiness()["ready"]
    rollback = context.registry.promote(context.model.version, 2, rollback=True)
    assert rollback.generation == 3
    assert process.refresh()
    assert process.predict(data.features[:3]).model_version == context.model.version
    assert process.predict(data.features[:3]).applied_generation == 3
    assert context.registry.audit()[-1]["action"] == "rollback"
    fresh = ServingProcess(
        context.registry, lambda _: (_ for _ in ()).throw(ValueError("load failed"))
    )
    assert not fresh.refresh()
    with pytest.raises(Unavailable):
        fresh.predict(data.features[:1])


def test_prediction_across_swap_binds_exact_captured_pipeline(context, data, split, monkeypatch):
    second = second_candidate(context, data, split)
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    expected = predict(context.trained.pipeline, data.features[:5])
    entered, release = threading.Event(), threading.Event()
    real_predict = serving_module.predict

    def paused(pipeline, matrix):
        if threading.current_thread().name.startswith("inference"):
            entered.set()
            assert release.wait(10)
        return real_predict(pipeline, matrix)

    monkeypatch.setattr(serving_module, "predict", paused)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="inference") as pool:
        pending = pool.submit(process.predict, data.features[:5])
        assert entered.wait(5)
        context.registry.promote(second.version, 1)
        assert process.refresh()
        release.set()
        prediction = pending.result(timeout=10)
    np.testing.assert_allclose(prediction.probabilities, expected, rtol=0, atol=1e-12)
    assert prediction.model_version == context.model.version
    assert prediction.artifact_digest == context.manifest.identity
    assert prediction.applied_generation == 1
    assert process.predict(data.features[:5]).applied_generation == 2


def test_http_predictions_match_offline_and_validate(context, data):
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    app = create_app(process, auto_refresh=False)
    records = [
        {
            f.name: None if np.isnan(value) else float(value)
            for f, value in zip(data.schema, row, strict=True)
        }
        for row in data.features[:10]
    ]
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.post("/predict", json={"records": records}).status_code == 503
        assert process.refresh()
        assert client.get("/ready").status_code == 200
        response = client.post("/predict", json={"records": records})
        assert response.status_code == 200
        document = response.json()
        np.testing.assert_allclose(
            document["probabilities"],
            predict(context.trained.pipeline, data.features[:10]),
            rtol=0,
            atol=1e-12,
        )
        assert document["model_version"] == context.model.version
        assert document["applied_generation"] == 1
        assert client.post("/predict", json={"records": [{"unknown": 1}]}).status_code == 422
        assert client.post("/predict", json={"records": []}).status_code == 422
        assert client.post("/predict", json={"records": records * 101}).status_code == 422
        assert client.get("/models?limit=1").json()[0]["version"] == context.model.version
        assert client.get("/models?limit=101").status_code == 422
        assert client.get("/deployment").json()["serving"]["ready"]


def test_actual_loopback_http_transport(context, data):
    import socket
    import time

    import httpx
    import uvicorn

    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen(16)
    config = uvicorn.Config(create_app(process), log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        record = {
            f.name: None if np.isnan(v) else float(v)
            for f, v in zip(data.schema, data.features[0], strict=True)
        }
        response = httpx.post(
            f"http://127.0.0.1:{port}/predict", json={"records": [record]}, timeout=5
        )
        assert response.status_code == 200
        assert response.json()["probabilities"] == pytest.approx(
            predict(context.trained.pipeline, data.features[:1]).tolist(), abs=1e-12
        )
        oversized = httpx.post(
            f"http://127.0.0.1:{port}/predict", content=b"x" * (2 * 1024 * 1024 + 1), timeout=5
        )
        assert oversized.status_code == 413
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


def test_successful_new_model_then_rollback_restores_prior_pipeline(context, data, split):
    second = second_candidate(context, data, split)
    process = ServingProcess(context.registry)
    context.registry.promote(context.model.version, 0)
    assert process.refresh()
    original = process.predict(data.features[:50])
    context.registry.promote(second.version, 1)
    assert process.refresh()
    changed = process.predict(data.features[:50])
    assert changed.model_version == second.version
    assert not np.array_equal(changed.probabilities, original.probabilities)
    context.registry.promote(context.model.version, 2, rollback=True)
    assert process.refresh()
    restored = process.predict(data.features[:50])
    assert restored.probabilities == original.probabilities
    assert restored.model_version == original.model_version
    assert restored.artifact_digest == original.artifact_digest
    assert restored.applied_generation == 3
