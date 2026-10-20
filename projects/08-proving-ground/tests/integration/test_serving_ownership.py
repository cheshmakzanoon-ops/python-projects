"""Controlled loader admission and terminal ownership of serving snapshots."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import pp_proving_ground.serving.service as module
from pp_proving_ground.serving.api import create_app
from pp_proving_ground.serving.service import ServingProcess, Unavailable


@pytest.mark.parametrize("fail", [False, True])
def test_same_generation_has_one_loader_and_shared_completion(context, monkeypatch, fail):
    context.registry.promote(context.model.version, 0)
    entered, release, followers = threading.Event(), threading.Event(), threading.Event()
    calls, waits = [], []
    actual_attempt = module._LoadAttempt

    class ObservedCompletion(threading.Event):
        def wait(self, timeout=None):
            waits.append(threading.get_ident())
            if len(waits) == 7:
                followers.set()
            return super().wait(timeout)

    monkeypatch.setattr(
        module, "_LoadAttempt", lambda: actual_attempt(complete=ObservedCompletion())
    )

    def loader(identity):
        calls.append(identity)
        entered.set()
        assert release.wait(10)
        if fail:
            raise ValueError("controlled load failure")
        return context.store.load(identity)

    process = ServingProcess(context.registry, loader)
    with ThreadPoolExecutor(max_workers=8) as pool:
        owner = pool.submit(process.refresh)
        assert entered.wait(5)
        waiting = [pool.submit(process.refresh) for _ in range(7)]
        try:
            assert followers.wait(5)
            assert len(calls) == 1
        finally:
            release.set()
        assert [future.result(timeout=10) for future in [owner, *waiting]] == [not fail] * 8
    assert process.readiness()["ready"] is not fail
    if fail:
        assert process.readiness()["load_error"] == "controlled load failure"
        # An explicit later refresh is a retry, rather than a cached permanent failure.
        assert not process.refresh()
        assert len(calls) == 2
    else:
        assert process.refresh()
        assert len(calls) == 1


def test_shutdown_prevents_a_late_loader_from_reviving_process(context, data):
    context.registry.promote(context.model.version, 0)
    entered, release = threading.Event(), threading.Event()

    def loader(identity):
        entered.set()
        assert release.wait(10)
        return context.store.load(identity)

    process = ServingProcess(context.registry, loader)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with TestClient(create_app(process, auto_refresh=False)):
            pending = pool.submit(process.refresh)
            assert entered.wait(5)
        release.set()
        assert pending.result(timeout=10) is False
    assert not process.readiness()["ready"]
    assert process.readiness()["closed"]
    assert not process.refresh()
    with pytest.raises(Unavailable, match="closed"):
        process.predict(data.features[:2])


def test_closing_wakes_waiting_refreshes_without_waiting_for_a_stuck_loader(context, monkeypatch):
    context.registry.promote(context.model.version, 0)
    entered, release, following = threading.Event(), threading.Event(), threading.Event()
    actual_attempt = module._LoadAttempt

    class ObservedCompletion(threading.Event):
        def wait(self, timeout=None):
            following.set()
            return super().wait(timeout)

    monkeypatch.setattr(
        module, "_LoadAttempt", lambda: actual_attempt(complete=ObservedCompletion())
    )

    def loader(identity):
        entered.set()
        assert release.wait(10)
        return context.store.load(identity)

    process = ServingProcess(context.registry, loader)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(process.refresh)
        assert entered.wait(5)
        follower = pool.submit(process.refresh)
        assert following.wait(5)
        try:
            process.close()
            assert follower.result(timeout=5) is False
            assert not owner.done()
        finally:
            release.set()
        assert owner.result(timeout=10) is False


def test_prediction_captured_before_close_can_finish_with_its_original_metadata(
    context, data, monkeypatch
):
    context.registry.promote(context.model.version, 0)
    process = ServingProcess(context.registry)
    assert process.refresh()
    expected = process.predict(data.features[:3])
    entered, release = threading.Event(), threading.Event()
    real_predict = module.predict

    def paused(pipeline, matrix):
        entered.set()
        assert release.wait(10)
        return real_predict(pipeline, matrix)

    monkeypatch.setattr(module, "predict", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(process.predict, data.features[:3])
        assert entered.wait(5)
        try:
            process.close()
            process.close()
            with pytest.raises(Unavailable):
                process.snapshot()
        finally:
            release.set()
        assert pending.result(timeout=10) == expected
