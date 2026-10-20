"""Reproducible lifecycle demo, benchmarks, and model-registry operations."""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import sqlite3
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from pp_proving_ground.artifacts.store import ArtifactError, ArtifactStore
from pp_proving_ground.data_contracts.schema import generate, read_parquet
from pp_proving_ground.evaluation.metrics import GatePolicy, evaluate
from pp_proving_ground.experiments.identity import ExperimentSpec, RunRecord, atomic_json
from pp_proving_ground.monitoring.drift import drift_report
from pp_proving_ground.registry.sqlite import PromotionRejected, Registry
from pp_proving_ground.reports.model_card import model_card
from pp_proving_ground.reports.provenance import (
    identity_for_source,
    project_directory,
    provenance,
    source_digest,
)
from pp_proving_ground.serving.service import ServingProcess
from pp_proving_ground.splits.manifest import SplitManifest, freeze
from pp_proving_ground.training.pipeline import PREPROCESSING, EstimatorName, fit, predict

OWNER = ".proving-ground-owned.json"


def prepare_output(output: Path) -> Path:
    if output.is_symlink():
        raise ValueError("symlink output refused")
    output = output.resolve()
    if output == Path(output.anchor) or output == Path.home() or output == Path.cwd():
        raise ValueError("output must be an isolated owned directory")
    if output.is_symlink():
        raise ValueError("symlink output refused")
    if output.exists() and any(output.iterdir()):
        if not (output / OWNER).is_file():
            raise ValueError("nonempty output directory is not owned by Proving Ground")
        raise ValueError("output already contains a run; choose another directory or clean-demo")
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / OWNER, {"owner": "pp-proving-ground", "format": 1, "path": str(output)})
    return output


def clean_output(output: Path) -> None:
    if output.is_symlink():
        raise ValueError("symlink output refused")
    target = output.resolve()
    marker = target / OWNER
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("refusing to remove directory without owned demo marker")
    document = json.loads(marker.read_text())
    if document != {"owner": "pp-proving-ground", "format": 1, "path": str(target)}:
        raise ValueError("ownership marker does not match directory")
    # Only known generated entries are removable. Unexpected user files block cleanup.
    allowed = {
        OWNER,
        "dataset.parquet",
        "split.json",
        "runs",
        "models",
        "registry.sqlite3",
        "registry.sqlite3-wal",
        "registry.sqlite3-shm",
        "report.json",
        "model-card.json",
        "benchmark.json",
        "predictions.json",
        "drift.json",
    }
    if set(p.name for p in target.iterdir()) - allowed:
        raise ValueError("unexpected files in demo directory; preserve and inspect them")
    shutil.rmtree(target)


def lifecycle(
    output: Path, rows: int, features: int, seed: int, profile: str = "demo"
) -> dict[str, Any]:
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
        if os.environ.get(name) != "1" and profile != "demo":
            raise ValueError(f"benchmark requires {name}=1")
    project = project_directory()
    evidence = provenance(
        project,
        profile,
        seed,
        {
            "rows": rows,
            "features": features,
            "assets": 50 if rows <= 5000 else 500,
            "purge_hours": 6,
            "embargo_hours": 2,
            "bootstrap_repetitions": 100,
            "estimators": ["prior", "logistic", "tree"],
            "threads": 1,
        },
    )
    initial_source = source_digest(project)
    output = prepare_output(output)
    t0 = time.perf_counter()
    data = generate(rows, features, 50 if rows <= 5000 else 500, seed, drift=0.4)
    data.write_parquet(output / "dataset.parquet")
    split = freeze(data)
    atomic_json(output / "split.json", {**asdict(split), "identity": split.identity})
    policy = GatePolicy()  # Frozen before any estimator is fitted or test judgment is computed.
    store = ArtifactStore(output / "models")
    registry = Registry(output / "registry.sqlite3", store, policy)
    code, lock = identity_for_source(project)
    reports: dict[str, Any] = {}
    results: dict[str, Any] = {}
    manifests: dict[str, Any] = {}
    versions: dict[str, Any] = {}
    training_times: dict[str, float] = {}
    artifact_sizes: dict[str, int] = {}
    estimators: tuple[EstimatorName, ...] = ("prior", "logistic", "tree")
    for estimator in estimators:
        name = estimator
        spec = ExperimentSpec(
            data.identity,
            split.identity,
            code,
            PREPROCESSING,
            estimator,
            {},
            seed,
            lock,
        )
        attempt = RunRecord.begin(spec, output / "runs", {"python": sys.version})
        start = time.perf_counter()
        trained = fit(data, split, estimator, seed)
        training_times[name] = time.perf_counter() - start
        manifest = store.publish(
            trained,
            spec.identity,
            data.identity,
            split.identity,
            tuple(f.name for f in data.schema),
        )
        report = evaluate(store, data, split, manifest.identity, seed=seed)
        version = registry.register(manifest.identity, report)
        reports[name], results[name], manifests[name], versions[name] = (
            report,
            trained,
            manifest,
            version,
        )
        artifact_sizes[name] = (store.path(manifest.identity) / "model.skops").stat().st_size
        atomic_json(
            output / "runs" / spec.identity / f"{attempt.attempt_id}-complete.json",
            {
                "artifact": manifest.identity,
                "evaluation": asdict(report),
                "version": version.version,
            },
        )
    rejected = False
    try:
        registry.promote(versions["prior"].version, 0)
    except PromotionRejected:
        rejected = True
    if not rejected:
        raise AssertionError("prior candidate should fail predeclared discrimination gates")
    passing = [name for name in ("logistic", "tree") if not policy.judge(reports[name])]
    if not passing:
        raise ValueError("no model passed predeclared validation policy")
    chosen = max(passing, key=lambda n: float(reports[n].metrics["pr_auc"]))
    previous = next((name for name in passing if name != chosen), chosen)
    registry.promote(versions[previous].version, 0)
    serving = ServingProcess(registry)
    if not serving.refresh():
        raise AssertionError("initial accepted model did not load")
    registry.promote(versions[chosen].version, 1)
    if not serving.refresh():
        raise AssertionError("selected candidate did not load")
    indices = split.indices("test")[: min(1000, len(split.test))]
    batch = data.features[indices]
    offline = predict(results[chosen].pipeline, batch)
    online = serving.predict(batch)
    parity = bool(np.allclose(offline, online.probabilities, rtol=0, atol=1e-12))
    if not parity:
        raise AssertionError("offline and served pipeline disagree")
    # Final-test report is descriptive and computed after candidate selection and promotion.
    final_test = evaluate(store, data, split, manifests[chosen].identity, role="test", seed=seed)
    serving.predict(batch)  # Warmup, then five independent timed inference repetitions.
    latencies: list[float] = []
    for _ in range(5):
        started = time.perf_counter()
        serving.predict(batch)
        latencies.append(time.perf_counter() - started)
    transition_times: list[float] = []
    # Alternate between previously deployed validation-qualified models. With the default seed,
    # this performs real tree/logistic pipeline swaps; every rollback creates a new generation.
    for repetition in range(5):
        rollback_target = previous if repetition % 2 == 0 else chosen
        started = time.perf_counter()
        registry.promote(
            versions[rollback_target].version, registry.current().generation, rollback=True
        )
        if not serving.refresh():
            raise AssertionError("rollback load failed")
        transition_times.append(time.perf_counter() - started)
    registry.promote(versions[chosen].version, registry.current().generation, rollback=True)
    if not serving.refresh():
        raise AssertionError("selected model restore failed")
    corruption_refused = corruption_probe(store, manifests[chosen].identity)
    drift = drift_report(
        data.features[split.indices("train")],
        data.features[split.indices("test")],
        tuple(f.name for f in data.schema),
        tuple(f.name for f in data.schema),
    )
    atomic_json(output / "drift.json", drift)
    atomic_json(output / "predictions.json", asdict(serving.predict(batch)))
    atomic_json(output / "model-card.json", model_card(reports[chosen], split, policy, registry))
    evidence.update(
        {
            "dataset_id": data.identity,
            "metrics": {
                "training_seconds": training_times,
                "artifact_bytes": artifact_sizes,
                "inference_seconds": latencies,
                "inference_median_seconds": statistics.median(latencies),
                "inference_p95_seconds": float(np.quantile(latencies, 0.95)),
                "inference_batch_rows": len(batch),
                "transition_seconds": transition_times,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
                "validation": {name: asdict(r) for name, r in reports.items()},
                "test_after_selection": asdict(final_test),
                "elapsed_seconds": time.perf_counter() - t0,
            },
            "correctness_checks": {
                "prior_rejected": rejected,
                "offline_serving_parity_atol_1e-12": parity,
                "corruption_refused": corruption_refused,
                "rollback_generation": registry.current().generation,
                "source_digest_unchanged": initial_source == source_digest(project),
            },
            "status": "passed",
            "chosen_model": chosen,
            "registry_audit": registry.audit(),
            "serving": serving.readiness(),
        }
    )
    if not all(evidence["correctness_checks"].values()):
        raise AssertionError("lifecycle correctness check failed")
    atomic_json(output / "report.json", evidence)
    if profile in {"ci", "standard"}:
        atomic_json(output / "benchmark.json", evidence)
    return evidence


def corruption_probe(store: ArtifactStore, identity: str) -> bool:
    # Corrupt a separate owned copy, preserving the immutable source artifact.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="pg-corruption-") as directory:
        other = ArtifactStore(Path(directory))
        shutil.copytree(store.path(identity), other.path(identity))
        with (other.path(identity) / "model.skops").open("ab") as stream:
            stream.write(b"corruption")
        try:
            other.load(identity)
        except ArtifactError:
            return True
        return False


def read_split(output: Path) -> SplitManifest:
    raw = json.loads((output / "split.json").read_text())
    identity = raw.pop("identity")
    for name in ("train", "validation", "test"):
        raw[name] = tuple(raw[name])
    split = SplitManifest(**raw)
    if split.identity != identity:
        raise ValueError("split manifest checksum mismatch")
    return split


def stage_generate(
    output: Path, rows: int, features: int, seed: int, policy: str
) -> dict[str, Any]:
    if policy not in {"temporal", "entity"}:
        raise ValueError("unsupported split policy")
    output = prepare_output(output)
    data = generate(rows, features, seed=seed)
    data.write_parquet(output / "dataset.parquet")
    split = freeze(data, "temporal" if policy == "temporal" else "entity")
    atomic_json(output / "split.json", {**asdict(split), "identity": split.identity})
    return {"dataset_digest": data.identity, "split_digest": split.identity}


def stage_train(
    output: Path, estimator: EstimatorName, seed: int, registry_path: Path | None = None
) -> dict[str, Any]:
    data = read_parquet(output / "dataset.parquet")
    split = read_split(output)
    split.validate(data)
    store = ArtifactStore(output / "models")
    registry = Registry(registry_path or output / "registry.sqlite3", store)
    code, lock = identity_for_source(project_directory())
    spec = ExperimentSpec(
        data.identity,
        split.identity,
        code,
        PREPROCESSING,
        estimator,
        {},
        seed,
        lock,
    )
    attempt = RunRecord.begin(spec, output / "runs", {"python": sys.version})
    trained = fit(data, split, estimator, seed)
    manifest = store.publish(
        trained, spec.identity, data.identity, split.identity, tuple(f.name for f in data.schema)
    )
    report = evaluate(store, data, split, manifest.identity, seed=seed)
    version = registry.register(manifest.identity, report)
    atomic_json(
        output / "runs" / spec.identity / f"{attempt.attempt_id}-complete.json",
        {"artifact": manifest.identity, "evaluation": asdict(report), "version": version.version},
    )
    return {
        "model_version": version.version,
        "artifact": manifest.identity,
        "evaluation": asdict(report),
        "promotion_failures": registry.policy.judge(report),
    }


def stage_evaluate(
    output: Path, version: int, role: str, registry_path: Path | None = None
) -> dict[str, Any]:
    if role not in {"validation", "test"}:
        raise ValueError("unknown evaluation role")
    data = read_parquet(output / "dataset.parquet")
    split = read_split(output)
    store = ArtifactStore(output / "models")
    registry = Registry(registry_path or output / "registry.sqlite3", store)
    model = next((m for m in registry.versions() if m.version == version), None)
    if model is None:
        raise ValueError("unknown model version")
    # Final-test evaluation follows an accepted deployment, never candidate selection.
    if role == "test" and not any(
        d["accepted"] and d["candidate_version"] == version for d in registry.audit()
    ):
        raise ValueError("final-test evaluation requires a previously promoted candidate")
    report = evaluate(
        store,
        data,
        split,
        model.artifact_digest,
        "validation" if role == "validation" else "test",
    )
    return asdict(report)


def stage_reevaluate_registry(
    output: Path,
    destination: Path,
    source_policy: GatePolicy | None = None,
) -> dict[str, Any]:
    """Retain old history, score actual artifacts, and create no deployment request."""
    if not destination.is_absolute():
        raise ValueError("destination registry must be an absolute fresh path")
    report_path = destination.with_name(destination.name + ".reevaluation.json")
    if report_path.exists():
        raise ValueError("reevaluation report already exists; choose a fresh destination")
    data = read_parquet(output / "dataset.parquet")
    split = read_split(output)
    split.validate(data)
    store = ArtifactStore(output / "models")
    source = Registry.open_read_only(output / "registry.sqlite3", store, source_policy)
    models = source.versions()
    policy = GatePolicy()  # Freeze independently of the reevaluated outcomes.
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    target = Registry(destination, store, policy)
    reevaluations: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for model in models:
        try:
            report = evaluate(store, data, split, model.artifact_digest)
            registered = target.register(model.artifact_digest, report)
            reevaluations.append(
                {
                    "source_version": model.version,
                    "target_version": registered.version,
                    "artifact_digest": model.artifact_digest,
                    "source_evaluation": model.evaluation_digest,
                    "target_evaluation": report.identity,
                    "promotion_failures": policy.judge(report),
                }
            )
        except (ValueError, OSError) as error:
            errors.append(
                {
                    "source_version": model.version,
                    "artifact_digest": model.artifact_digest,
                    "error": str(error),
                }
            )
    result = {
        "format_version": 1,
        "status": "partial" if errors else "completed",
        "source_registry": str(source.path.resolve()),
        "target_registry": str(destination.resolve()),
        "source_policy": source.policy.identity,
        "target_policy": policy.identity,
        "source_deployment": asdict(source.current()),
        "target_deployment": asdict(target.current()),
        "dataset_digest": data.identity,
        "split_digest": split.identity,
        "reevaluations": reevaluations,
        "errors": errors,
    }
    atomic_json(report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["demo", "benchmark", "clean-demo"]:
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name != "clean-demo":
            command.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            command.add_argument("--profile", choices=["ci", "standard"], default="ci")
    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--rows", type=int, default=5000)
    generate_parser.add_argument("--features", type=int, default=12)
    generate_parser.add_argument("--seed", type=int, default=1729)
    generate_parser.add_argument(
        "--split-policy", choices=["temporal", "entity"], default="temporal"
    )
    train_parser = sub.add_parser("train")
    train_parser.add_argument("--output", type=Path, required=True)
    train_parser.add_argument(
        "--estimator", choices=["prior", "logistic", "tree"], default="logistic"
    )
    train_parser.add_argument("--seed", type=int, default=1729)
    train_parser.add_argument("--registry", type=Path)
    eval_parser = sub.add_parser("evaluate")
    eval_parser.add_argument("--output", type=Path, required=True)
    eval_parser.add_argument("--version", type=int, required=True)
    eval_parser.add_argument("--role", choices=["validation", "test"], default="validation")
    eval_parser.add_argument("--registry", type=Path)
    for name in ["model-card", "drift"]:
        report_parser = sub.add_parser(name)
        report_parser.add_argument("--output", type=Path, required=True)
        if name == "drift":
            report_parser.add_argument("--incoming", type=Path, required=True)
        else:
            report_parser.add_argument("--registry", type=Path)
    reassess = sub.add_parser("reevaluate-registry")
    reassess.add_argument("--output", type=Path, required=True)
    reassess.add_argument("--destination", type=Path, required=True)
    reassess.add_argument("--source-policy", type=Path)
    serve = sub.add_parser("serve")
    serve.add_argument("--output", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8108)
    serve.add_argument("--registry", type=Path)
    for name in ["inspect", "promote", "rollback", "predict"]:
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--registry", type=Path)
        if name in {"promote", "rollback"}:
            command.add_argument("--version", type=int, required=True)
            command.add_argument("--expected-generation", type=int, required=True)
        if name == "predict":
            command.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    selected_registry = getattr(args, "registry", None) or args.output / "registry.sqlite3"
    try:
        if args.command == "reevaluate-registry":
            policy = (
                GatePolicy(**json.loads(args.source_policy.read_text()))
                if args.source_policy
                else None
            )
            result = stage_reevaluate_registry(args.output, args.destination, policy)
            print(json.dumps(result))
            return 1 if result["errors"] else 0
        if args.command == "generate":
            print(
                json.dumps(
                    stage_generate(
                        args.output, args.rows, args.features, args.seed, args.split_policy
                    )
                )
            )
            return 0
        if args.command == "train":
            print(
                json.dumps(stage_train(args.output, args.estimator, args.seed, selected_registry))
            )
            return 0
        if args.command == "evaluate":
            print(
                json.dumps(stage_evaluate(args.output, args.version, args.role, selected_registry))
            )
            return 0
        if args.command == "model-card":
            registry = Registry(selected_registry, ArtifactStore(args.output / "models"))
            version = registry.current().model_version
            if version is None:
                raise ValueError("model-card requires a deployed version")
            print(
                json.dumps(
                    model_card(
                        registry.report(version), read_split(args.output), registry.policy, registry
                    )
                )
            )
            return 0
        if args.command == "drift":
            reference = read_parquet(args.output / "dataset.parquet")
            incoming = read_parquet(args.incoming)
            print(
                json.dumps(
                    drift_report(
                        reference.features,
                        incoming.features,
                        tuple(f.name for f in reference.schema),
                        tuple(f.name for f in incoming.schema),
                    )
                )
            )
            return 0
        if args.command == "clean-demo":
            clean_output(args.output)
            return 0
        if args.command in {"demo", "benchmark"}:
            standard = args.command == "benchmark" and args.profile == "standard"
            result = lifecycle(
                args.output,
                250000 if standard else 5000,
                40 if standard else 12,
                args.seed,
                args.profile if args.command == "benchmark" else "demo",
            )
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output": str(args.output.resolve()),
                        "chosen_model": result["chosen_model"],
                        "serving": result["serving"],
                    }
                )
            )
            return 0
        store = ArtifactStore(args.output / "models")
        registry = (
            Registry.open_read_only(selected_registry, store)
            if args.command == "inspect"
            else Registry(selected_registry, store)
        )
        if args.command in {"promote", "rollback"}:
            result = asdict(
                registry.promote(
                    args.version, args.expected_generation, rollback=args.command == "rollback"
                )
            )
            print(json.dumps(result))
        elif args.command == "inspect":
            print(
                json.dumps(
                    {
                        "registry_path": str(registry.path.resolve()),
                        "versions": [asdict(v) for v in registry.versions()],
                        "deployment": asdict(registry.current()),
                        "audit": registry.audit(),
                    }
                )
            )
        else:
            process = ServingProcess(registry)
            process.refresh()
            if args.command == "predict":
                if args.input.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("prediction input exceeds 2 MiB")
                print(
                    json.dumps(asdict(process.predict_records(json.loads(args.input.read_text()))))
                )
            else:
                import uvicorn

                from pp_proving_ground.serving.api import create_app

                uvicorn.run(create_app(process), host="127.0.0.1", port=args.port)
        return 0
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as error:
        print(f"proving-ground: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
