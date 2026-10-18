"""Immutable, content-addressed, checksum-verified, type-reviewed skops artifacts.

The supported estimator set contains only built-in sklearn pipeline components.
No external Python classes are approved. A checksum is integrity, never a trust grant.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import skops.io as sio
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from pp_proving_ground.experiments.identity import canonical, digest, file_hash
from pp_proving_ground.training.pipeline import TrainingResult

# Reviewed data-only dtype descriptors and sklearn native decision-tree node storage.
# No custom estimator, transformer, callable or user-specified module is trusted.
REVIEWED_TYPES = frozenset({"numpy.dtype", "sklearn.tree._tree.Tree"})


class ArtifactError(ValueError):
    pass


def environment_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in ["scikit-learn", "numpy", "skops"]}


@dataclass(frozen=True)
class ArtifactManifest:
    format_version: int
    model_sha256: str
    run_identity: str
    dataset_digest: str
    split_digest: str
    feature_names: tuple[str, ...]
    estimator: str
    environment: dict[str, str]
    serialization: str = "skops-reviewed-v1"

    @property
    def identity(self) -> str:
        return digest(asdict(self))


class ArtifactStore:
    max_model_bytes = 64 * 1024 * 1024

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, identity: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
            raise ArtifactError("invalid artifact identity")
        return self.root / identity

    def publish(
        self,
        result: TrainingResult,
        run: str,
        dataset: str,
        split: str,
        names: tuple[str, ...],
        interrupt_before_publish: bool = False,
    ) -> ArtifactManifest:
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=self.root))
        try:
            model = stage / "model.skops"
            sio.dump(result.pipeline, model)
            unknown = sio.get_untrusted_types(file=model)
            if set(unknown) - REVIEWED_TYPES:
                raise ArtifactError(f"unreviewed model types: {unknown}")
            with model.open("rb") as stream:
                os.fsync(stream.fileno())
            manifest = ArtifactManifest(
                1,
                file_hash(model),
                run,
                dataset,
                split,
                names,
                result.estimator,
                environment_versions(),
            )
            with (stage / "manifest.json").open("xb") as stream:
                stream.write(canonical(asdict(manifest)))
                stream.flush()
                os.fsync(stream.fileno())
            if interrupt_before_publish:
                raise InterruptedError("injected interruption before artifact publication")
            destination = self.path(manifest.identity)
            try:
                os.rename(stage, destination)
            except OSError:
                if not destination.is_dir():
                    raise
                self.inspect(manifest.identity)
            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def inspect(self, identity: str) -> ArtifactManifest:
        directory = self.path(identity)
        manifest_path, model = directory / "manifest.json", directory / "model.skops"
        if directory.is_symlink() or manifest_path.is_symlink() or model.is_symlink():
            raise ArtifactError("symlink artifacts prohibited")
        try:
            if manifest_path.stat().st_size > 65536 or model.stat().st_size > self.max_model_bytes:
                raise ArtifactError("artifact size limit")
            raw: dict[str, Any] = json.loads(manifest_path.read_text())
            raw["feature_names"] = tuple(raw["feature_names"])
            manifest = ArtifactManifest(**raw)
            if manifest.identity != identity or file_hash(model) != manifest.model_sha256:
                raise ArtifactError("artifact checksum mismatch")
            if manifest.format_version != 1 or manifest.serialization != "skops-reviewed-v1":
                raise ArtifactError("unsupported artifact format")
            if manifest.estimator not in {"prior", "logistic", "tree"}:
                raise ArtifactError("unsupported estimator")
            if manifest.environment != environment_versions():
                raise ArtifactError("unsupported persistence-library versions")
            return manifest
        except (OSError, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ArtifactError("invalid/incomplete artifact") from error

    def load(self, identity: str) -> tuple[Pipeline, ArtifactManifest]:
        manifest = self.inspect(identity)
        model_path = self.path(identity) / "model.skops"
        # Read once after checksum and recheck the exact bytes passed to the deserializer.
        data = model_path.read_bytes()
        import hashlib

        if hashlib.sha256(data).hexdigest() != manifest.model_sha256:
            raise ArtifactError("artifact changed during load")
        try:
            # Bound the expanded archive before skops parses its schema/type metadata.
            with zipfile.ZipFile(BytesIO(data)) as archive:
                members = archive.infolist()
                if (
                    len(members) > 4096
                    or sum(info.file_size for info in members) > 256 * 1024 * 1024
                ):
                    raise ArtifactError("expanded artifact size limit")
            unknown = sio.get_untrusted_types(data=data)
            if set(unknown) - REVIEWED_TYPES:
                raise ArtifactError(f"unreviewed serialization types: {unknown}")
            pipeline = sio.loads(data, trusted=list(REVIEWED_TYPES))
            if not isinstance(pipeline, Pipeline):
                raise ArtifactError("expected supported complete pipeline")
            expected = {"imputer", "scaler", "classifier"}
            if set(pipeline.named_steps) != expected:
                raise ArtifactError("unsupported pipeline components")
            if (
                type(pipeline.named_steps["imputer"]) is not SimpleImputer
                or type(pipeline.named_steps["scaler"]) is not StandardScaler
            ):
                raise ArtifactError("unsupported preprocessing types")
            classifiers = {
                "prior": DummyClassifier,
                "logistic": LogisticRegression,
                "tree": DecisionTreeClassifier,
            }
            if type(pipeline.named_steps["classifier"]) is not classifiers[manifest.estimator]:
                raise ArtifactError("unsupported classifier type")
            return pipeline, manifest
        except ArtifactError:
            raise
        except Exception as error:
            raise ArtifactError("invalid skops serialization") from error

    def recover_staging(self) -> int:
        """Call only under exclusive ownership; never touch published content."""
        count = 0
        for path in self.root.glob(".stage-*"):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
                count += 1
        return count
