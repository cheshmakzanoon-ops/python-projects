"""SQLite owns model identity, immutable reports and conditional deployment transitions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from pp_proving_ground.artifacts.store import ArtifactStore
from pp_proving_ground.evaluation.metrics import EvaluationReport, GatePolicy
from pp_proving_ground.experiments.identity import canonical, digest


@dataclass(frozen=True)
class ModelVersion:
    version: int
    artifact_digest: str
    dataset_digest: str
    split_digest: str
    evaluation_digest: str


@dataclass(frozen=True)
class DeploymentGeneration:
    generation: int
    model_version: int | None
    artifact_digest: str | None


@dataclass(frozen=True)
class PromotionDecision:
    candidate_version: int
    artifact_digest: str
    dataset_digest: str
    split_digest: str
    evaluation_digest: str
    policy_digest: str
    expected_generation: int
    accepted: bool
    reasons: tuple[str, ...]
    action: str


class PromotionRejected(ValueError):
    def __init__(self, decision: PromotionDecision):
        self.decision = decision
        super().__init__("; ".join(decision.reasons))


class Registry:
    def __init__(self, path: Path, store: ArtifactStore, policy: GatePolicy = GatePolicy()):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.store, self.policy = path, store, policy
        with self.connection() as conn:
            self._validate_format(conn)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._validate_format(conn)
                statements = [
                    "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS models(version INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "artifact TEXT UNIQUE NOT NULL, dataset TEXT NOT NULL, split TEXT NOT NULL, "
                    "evaluation TEXT NOT NULL, report TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS deployment(generation INTEGER PRIMARY KEY, "
                    "version INTEGER NOT NULL REFERENCES models(version), action TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, decision TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "created_at TEXT NOT NULL, decision TEXT NOT NULL)",
                ]
                for statement in statements:
                    conn.execute(statement)
                conn.execute("PRAGMA application_id=1347430193")
                conn.execute("PRAGMA user_version=1")
                conn.execute(
                    "INSERT OR IGNORE INTO settings VALUES('policy', ?)", (policy.identity,)
                )
                stored = conn.execute("SELECT value FROM settings WHERE key='policy'").fetchone()
                if stored is None or stored[0] != policy.identity:
                    raise ValueError(
                        "registry policy differs from frozen policy; create explicit new registry"
                    )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    @staticmethod
    def _validate_format(conn: sqlite3.Connection) -> None:
        application = conn.execute("PRAGMA application_id").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if application == 1347430193 and version == 1:
            if not {"settings", "models", "deployment", "audit"} <= tables:
                raise ValueError("incomplete registry schema")
            return
        if application == 0 and version == 0 and not tables:
            return
        raise ValueError("unsupported registry application/schema version")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        try:
            yield conn
        finally:
            conn.close()

    def register(self, artifact: str, report: EvaluationReport) -> ModelVersion:
        manifest = self.store.inspect(artifact)
        if (report.artifact_digest, report.dataset_digest, report.split_digest) != (
            artifact,
            manifest.dataset_digest,
            manifest.split_digest,
        ):
            raise ValueError("evaluation does not bind this candidate/data/split")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                prior = conn.execute(
                    "SELECT * FROM models WHERE artifact=?", (artifact,)
                ).fetchone()
                if prior is not None:
                    if prior["evaluation"] != report.identity:
                        raise ValueError("immutable model already bound to another evaluation")
                    conn.commit()
                    return self._version(prior)
                cursor = conn.execute(
                    "INSERT INTO models(artifact,dataset,split,evaluation,report) "
                    "VALUES(?,?,?,?,?)",
                    (
                        artifact,
                        manifest.dataset_digest,
                        manifest.split_digest,
                        report.identity,
                        canonical(asdict(report)).decode(),
                    ),
                )
                version = int(cursor.lastrowid or 0)
                conn.commit()
                return ModelVersion(
                    version,
                    artifact,
                    manifest.dataset_digest,
                    manifest.split_digest,
                    report.identity,
                )
            except BaseException:
                conn.rollback()
                raise

    @staticmethod
    def _version(row: sqlite3.Row) -> ModelVersion:
        return ModelVersion(
            int(row["version"]), row["artifact"], row["dataset"], row["split"], row["evaluation"]
        )

    def report(self, version: int) -> EvaluationReport:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT report,evaluation FROM models WHERE version=?", (version,)
            ).fetchone()
            if row is None:
                raise ValueError("unknown model version")
            raw = json.loads(row["report"])
            raw["calibration"], raw["slices"] = tuple(raw["calibration"]), tuple(raw["slices"])
            report = EvaluationReport(**raw)
            if report.identity != row["evaluation"]:
                raise ValueError("stored evaluation integrity mismatch")
            return report

    def versions(self) -> tuple[ModelVersion, ...]:
        with self.connection() as conn:
            return tuple(
                self._version(r) for r in conn.execute("SELECT * FROM models ORDER BY version")
            )

    @staticmethod
    def _current(conn: sqlite3.Connection) -> DeploymentGeneration:
        row = conn.execute(
            "SELECT d.generation,d.version,m.artifact FROM deployment d JOIN models m "
            "ON d.version=m.version ORDER BY d.generation DESC LIMIT 1"
        ).fetchone()
        return (
            DeploymentGeneration(0, None, None)
            if row is None
            else DeploymentGeneration(int(row["generation"]), int(row["version"]), row["artifact"])
        )

    def current(self) -> DeploymentGeneration:
        with self.connection() as conn:
            return self._current(conn)

    def promote(
        self,
        version: int,
        expected_generation: int,
        evaluation_digest: str | None = None,
        rollback: bool = False,
    ) -> DeploymentGeneration:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                current = self._current(conn)
                row = conn.execute("SELECT * FROM models WHERE version=?", (version,)).fetchone()
                if row is None:
                    raise ValueError("unknown model version")
                report_raw: dict[str, Any] = json.loads(row["report"])
                report_raw["calibration"] = tuple(report_raw["calibration"])
                report_raw["slices"] = tuple(report_raw["slices"])
                report = EvaluationReport(**report_raw)
                reasons = list(self.policy.judge(report))
                frozen_policy = conn.execute(
                    "SELECT value FROM settings WHERE key='policy'"
                ).fetchone()
                if frozen_policy is None or frozen_policy[0] != self.policy.identity:
                    reasons.append("promotion policy differs from frozen registry policy")
                if report.identity != row["evaluation"]:
                    reasons.append("stored evaluation integrity mismatch")
                if evaluation_digest is not None and evaluation_digest != row["evaluation"]:
                    reasons.append("requested evaluation is not candidate evaluation")
                if (report.artifact_digest, report.dataset_digest, report.split_digest) != (
                    row["artifact"],
                    row["dataset"],
                    row["split"],
                ):
                    reasons.append("evaluation/candidate binding mismatch")
                if current.generation != expected_generation:
                    reasons.append("registry generation comparison failed")
                if (
                    rollback
                    and conn.execute(
                        "SELECT 1 FROM deployment WHERE version=?", (version,)
                    ).fetchone()
                    is None
                ):
                    reasons.append("rollback target has never been deployed")
                # Recheck immutable manifest integrity before recording a request. Load occurs separately.
                try:
                    self.store.inspect(row["artifact"])
                except ValueError as error:
                    reasons.append(f"artifact verification: {error}")
                decision = PromotionDecision(
                    version,
                    row["artifact"],
                    row["dataset"],
                    row["split"],
                    row["evaluation"],
                    self.policy.identity,
                    expected_generation,
                    not reasons,
                    tuple(reasons),
                    "rollback" if rollback else "promote",
                )
                encoded = canonical(asdict(decision)).decode()
                now = datetime.now(UTC).isoformat()
                conn.execute("INSERT INTO audit(created_at,decision) VALUES(?,?)", (now, encoded))
                if reasons:
                    conn.commit()
                    raise PromotionRejected(decision)
                generation = current.generation + 1
                conn.execute(
                    "INSERT INTO deployment VALUES(?,?,?,?,?)",
                    (generation, version, decision.action, now, encoded),
                )
                conn.commit()
                return DeploymentGeneration(generation, version, row["artifact"])
            except BaseException:
                if conn.in_transaction:
                    conn.rollback()
                raise

    def audit(self) -> tuple[dict[str, Any], ...]:
        with self.connection() as conn:
            return tuple(
                json.loads(row[0])
                for row in conn.execute("SELECT decision FROM audit ORDER BY seq")
            )

    @property
    def policy_digest(self) -> str:
        return digest(asdict(self.policy))
