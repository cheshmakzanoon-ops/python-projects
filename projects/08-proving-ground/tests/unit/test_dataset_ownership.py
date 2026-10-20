"""Frozen dataset content must survive writes through all caller-owned aliases."""

from dataclasses import replace

import numpy as np
import pytest


@pytest.mark.parametrize(
    "field",
    [
        "row_ids",
        "assets",
        "observed_at",
        "feature_available_at",
        "label_available_at",
        "features",
        "labels",
    ],
)
def test_dataset_owns_an_immutable_snapshot(data, field):
    # Sliced backing arrays expose the bug even when the supplied view is read-only.
    original = getattr(data, field)
    backing = np.repeat(original, 2, axis=0)
    supplied = backing[::2]
    frozen = replace(data, **{field: supplied})
    before = getattr(frozen, field).copy()
    identity = frozen.identity
    backing[...] = 0
    np.testing.assert_array_equal(getattr(frozen, field), before)
    assert frozen.identity == identity
    with pytest.raises(ValueError):
        getattr(frozen, field).setflags(write=True)


@pytest.mark.parametrize("metadata", ["shape", "dtype", "strides"])
def test_modified_numpy_layout_cannot_reuse_frozen_identity(data, metadata):
    from pp_proving_ground.data_contracts.schema import ContractError

    frozen = replace(data)
    if metadata == "shape":
        with pytest.warns(DeprecationWarning):
            frozen.features.shape = (1, frozen.features.size)
    elif metadata == "dtype":
        with pytest.warns(DeprecationWarning):
            frozen.features.dtype = np.int64
    else:
        with pytest.warns(DeprecationWarning):
            frozen.features.strides = (0, frozen.features.strides[1])
    with pytest.raises(ContractError, match="layout was modified"):
        _ = frozen.identity
    with pytest.raises(ContractError, match="layout was modified"):
        frozen.validate_availability()
