from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pp_proving_ground.data_contracts.schema import ContractError, generate
from pp_proving_ground.evaluation.metrics import calibration, metrics
from pp_proving_ground.splits.manifest import freeze


@given(st.integers(min_value=0, max_value=2**31 - 1), st.sampled_from(["temporal", "entity"]))
@settings(max_examples=25, deadline=None)
def test_generated_splits_partition_without_leakage(seed, policy):
    data = generate(rows=1000, assets=10, seed=seed)
    split = freeze(data, policy)
    split.validate(data)
    membership = split.train + split.validation + split.test
    assert len(set(membership)) == len(membership)
    assert all(0 <= i < 1000 for i in membership)
    assert freeze(data, policy).identity == split.identity
    if policy == "temporal":
        assert all(data.label_available_at[i] < split.validation_boundary for i in split.train)
        assert all(
            data.observed_at[i] >= split.test_boundary + split.embargo_hours for i in split.test
        )
    else:
        assert not (set(data.assets[list(split.train)]) & set(data.assets[list(split.test)]))
    with pytest.raises(ContractError):
        replace(split, test=split.test + (split.train[0],)).validate(data)


@given(
    st.lists(
        st.tuples(st.integers(0, 1), st.floats(min_value=0, max_value=1, allow_nan=False)),
        min_size=1,
        max_size=100,
    )
)
@settings(max_examples=50, deadline=None)
def test_calibration_conserves_samples_and_brier_independent(pairs):
    y = np.array([a for a, _ in pairs], dtype=np.int64)
    p = np.array([b for _, b in pairs], dtype=np.float64)
    report = metrics(y, p)
    assert sum(b["count"] for b in calibration(y, p)) == len(pairs)
    independent = sum((b - a) ** 2 for a, b in pairs) / len(pairs)
    assert report["brier"] == pytest.approx(independent)
    assert 0 <= report["brier"] <= 1
