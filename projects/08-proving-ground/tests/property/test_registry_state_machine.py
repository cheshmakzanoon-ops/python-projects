"""Generated deployment histories checked against a small independent integer model."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from pp_proving_ground.artifacts.store import ArtifactStore
from pp_proving_ground.data_contracts.schema import generate
from pp_proving_ground.evaluation.metrics import evaluate
from pp_proving_ground.registry.sqlite import PromotionRejected, Registry
from pp_proving_ground.splits.manifest import freeze
from pp_proving_ground.training.pipeline import fit


@lru_cache(maxsize=1)
def fixture():
    data = generate(rows=2000, assets=20)
    split = freeze(data)
    return data, split, fit(data, split, "logistic")


class RegistryHistory(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.temporary = tempfile.TemporaryDirectory(prefix="pg-state-")
        root = Path(self.temporary.name)
        data, split, trained = fixture()
        store = ArtifactStore(root / "models")
        self.registry = Registry(root / "registry.db", store)
        self.models = []
        for i in range(2):
            manifest = store.publish(
                trained,
                str(i) * 64,
                data.identity,
                split.identity,
                tuple(f.name for f in data.schema),
            )
            report = evaluate(store, data, split, manifest.identity, bootstrap_repetitions=3)
            if i == 1:
                report = replace(report, metrics={**report.metrics, "roc_auc": None})
            self.models.append(self.registry.register(manifest.identity, report))
        self.generation = 0
        self.version = None
        self.audit_length = 0

    @rule(candidate=st.integers(0, 1), stale=st.booleans(), rollback=st.booleans())
    def transition(self, candidate, stale, rollback):
        expected = self.generation - 1 if stale else self.generation
        should_succeed = candidate == 0 and not stale and (not rollback or self.generation > 0)
        try:
            result = self.registry.promote(
                self.models[candidate].version, expected, rollback=rollback
            )
        except PromotionRejected:
            assert not should_succeed
        else:
            assert should_succeed
            self.generation += 1
            self.version = self.models[candidate].version
            assert result.generation == self.generation
        self.audit_length += 1

    @invariant()
    def persisted_state_matches_integer_reference(self):
        restarted = Registry(self.registry.path, self.registry.store)
        assert restarted.current().generation == self.generation
        assert restarted.current().model_version == self.version
        assert len(restarted.audit()) == self.audit_length
        assert sum(a["accepted"] for a in restarted.audit()) == self.generation

    def teardown(self):
        self.temporary.cleanup()


TestRegistryHistory = RegistryHistory.TestCase
TestRegistryHistory.settings = settings(max_examples=10, stateful_step_count=20, deadline=None)
