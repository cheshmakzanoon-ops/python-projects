"""A fitted result cannot be mislabeled as another experiment's dataset or split."""

from dataclasses import replace

import pytest

from pp_proving_ground.artifacts.store import ArtifactError


@pytest.mark.parametrize("changed", ["dataset", "split", "names"])
def test_publication_rejects_fit_provenance_mismatch(context, data, split, changed):
    dataset, membership = data.identity, split.identity
    names = tuple(f.name for f in data.schema)
    if changed == "dataset":
        dataset = "d" * 64
    elif changed == "split":
        membership = replace(split, question=split.question + " Another question.").identity
    else:
        names = tuple(reversed(names))
    before = set(context.store.root.iterdir())
    with pytest.raises(ArtifactError, match="fit provenance"):
        context.store.publish(context.trained, "f" * 64, dataset, membership, names)
    assert set(context.store.root.iterdir()) == before


def test_evaluation_scores_persisted_prior_even_when_original_fit_is_replaced(context, data, split):
    from pp_proving_ground.evaluation.metrics import GatePolicy, evaluate
    from pp_proving_ground.training.pipeline import fit

    prior = fit(data, split, "prior")
    manifest = context.store.publish(
        prior, "c" * 64, data.identity, split.identity, prior.feature_names
    )
    # Mutating the caller-owned TrainingResult cannot substitute the published pipeline.
    prior.pipeline.steps = context.trained.pipeline.steps
    report = evaluate(context.store, data, split, manifest.identity, bootstrap_repetitions=3)
    assert report.metrics["roc_auc"] == 0.5
    assert report.metrics["pr_auc"] == report.metrics["class_balance"]
    assert GatePolicy().judge(report)
    version = context.registry.register(manifest.identity, report)
    from pp_proving_ground.registry.sqlite import PromotionRejected

    with pytest.raises(PromotionRejected):
        context.registry.promote(version.version, 0)


def test_evaluation_refuses_other_dataset_and_changed_membership(context, data, split):
    from pp_proving_ground.data_contracts.schema import generate
    from pp_proving_ground.evaluation.metrics import evaluate
    from pp_proving_ground.splits.manifest import freeze

    changed = generate(seed=19)
    for candidate, membership in [
        (changed, freeze(changed)),
        (data, replace(split, validation=split.validation[:-1])),
    ]:
        with pytest.raises(ValueError, match="fit provenance"):
            evaluate(
                context.store,
                candidate,
                membership,
                context.manifest.identity,
                bootstrap_repetitions=3,
            )


def test_invalid_serialized_pipeline_is_refused_before_publication(context, data, split):
    import copy

    from pp_proving_ground.training.pipeline import fit

    candidate = copy.deepcopy(fit(data, split, "prior"))
    candidate.pipeline.named_steps["classifier"].class_prior_[:] = [0.2, 0.2]
    before = set(context.store.root.iterdir())
    with pytest.raises(ArtifactError):
        context.store.publish(
            candidate, "d" * 64, data.identity, split.identity, candidate.feature_names
        )
    assert set(context.store.root.iterdir()) == before
