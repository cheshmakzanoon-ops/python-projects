"""Reviewable multi-file plans with hash checks and recoverable application journal.

Each file replacement is atomic; a sequence of files is not one atomic operation.
A journal and backups support process-interruption recovery; power-loss durability
is not established because directory and journal persistence is not forced.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pp_pytrace.codemods.transforms import rewrite
from pp_pytrace.frontend.discovery import Limits, decode_source, parse, read_bounded, read_source


@dataclass(frozen=True)
class Edit:
    path: str
    original_sha256: str
    replacement: str


@dataclass(frozen=True)
class Plan:
    root: str
    edits: tuple[Edit, ...]
    abstentions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "root": self.root,
            "edits": [asdict(edit) for edit in self.edits],
            "abstentions": self.abstentions,
        }


def guarded_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        not relative
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in relative
        or ":" in relative
        or relative != pure.as_posix()
    ):
        raise ValueError("malformed/path-escaping edit")
    target = root / relative
    if not target.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError("path-escaping edit")
    if any(part.is_symlink() for part in [target, *list(target.parents)[: len(pure.parts) - 1]]):
        raise ValueError("symlink edit refused")
    if not target.is_file() or target.suffix != ".py":
        raise ValueError("edits require selected Python regular files")
    return target


def create_plan(root: Path, selected: list[str]) -> Plan:
    root = root.resolve(strict=True)
    if len(set(selected)) != len(selected):
        raise ValueError("overlapping selected edits")
    edits = []
    abstentions = []
    for relative in sorted(selected):
        path = guarded_path(root, relative)
        data = read_bounded(path)
        if data.startswith(b"\xef\xbb\xbf") or b"coding:" in data[:200] or b"coding=" in data[:200]:
            abstentions.append(relative + ": non-plain-UTF8 encoding requires manual review")
            continue
        source = decode_source(data)
        change = rewrite(source)
        abstentions.extend(relative + ": " + item for item in change.abstentions)
        if change.after != source:
            edits.append(Edit(relative, hashlib.sha256(data).hexdigest(), change.after))
    return Plan(str(root), tuple(edits), tuple(abstentions))


def patch(plan: Plan) -> str:
    result: list[str] = []
    for edit in plan.edits:
        path = guarded_path(Path(plan.root), edit.path)
        old = read_source(path)
        result.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                edit.replacement.splitlines(keepends=True),
                fromfile="a/" + edit.path,
                tofile="b/" + edit.path,
            )
        )
    return "".join(result)


def load_plan(path: Path) -> Plan:
    data = json.loads(read_bounded(path, 4_000_000).decode("utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or not isinstance(data.get("root"), str)
        or not isinstance(data.get("edits"), list)
    ):
        raise ValueError("malformed plan")
    edits = []
    for item in data["edits"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "original_sha256", "replacement"}
            or not all(isinstance(value, str) for value in item.values())
        ):
            raise ValueError("malformed edit")
        edits.append(Edit(**item))
    return Plan(data["root"], tuple(edits))


def _write_atomic(path: Path, data: bytes) -> None:
    handle = tempfile.NamedTemporaryFile(
        prefix=".pytrace-", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, path.stat().st_mode)
        temporary.replace(path)
    finally:
        # Unique names permit recovery after an interrupted earlier replacement.
        # Remove only this invocation's temporary, never another writer's file.
        temporary.unlink(missing_ok=True)


def apply(plan: Plan, journal: Path) -> None:
    root = Path(plan.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("plan root must be a directory")
    if len({edit.path for edit in plan.edits}) != len(plan.edits):
        raise ValueError("overlapping edits")
    verified: list[tuple[Path, bytes, bytes]] = []
    for edit in plan.edits:
        path = guarded_path(root, edit.path)
        original = read_bounded(path)
        if hashlib.sha256(original).hexdigest() != edit.original_sha256:
            raise ValueError("stale original content hash")
        parse(edit.replacement, edit.path, Limits())
        # Recompute eligibility; a caller cannot smuggle arbitrary replacements through a JSON plan.
        expected = rewrite(original.decode("utf-8")).after
        if edit.replacement != expected:
            raise ValueError("replacement does not match verified conservative transformation")
        verified.append((path, original, edit.replacement.encode("utf-8")))
    journal.mkdir(parents=True, exist_ok=False)
    manifest: list[dict[str, str]] = []
    for index, (path, original, replacement) in enumerate(verified):
        backup = journal / f"{index}.backup"
        backup.write_bytes(original)
        manifest.append(
            {
                "path": path.relative_to(root).as_posix(),
                "backup": backup.name,
                "before": hashlib.sha256(original).hexdigest(),
                "after": hashlib.sha256(replacement).hexdigest(),
            }
        )
    (journal / "plan.json").write_text(
        json.dumps(
            {"schema_version": 1, "root": str(root), "files": manifest, "status": "prepared"},
            indent=2,
        )
    )
    for path, original, replacement in verified:
        if read_bounded(path) != original:
            raise ValueError("content changed during apply; recover using journal")
        _write_atomic(path, replacement)
    (journal / "complete").write_text("all file replacements completed\n")


def recover(journal: Path) -> None:
    data = json.loads(read_bounded(journal / "plan.json", 4_000_000).decode("utf-8"))
    root = Path(data["root"]).resolve(strict=True)
    verified = []
    for item in data["files"]:
        path = guarded_path(root, item["path"])
        content = read_bounded(path)
        if hashlib.sha256(content).hexdigest() not in (item["before"], item["after"]):
            raise ValueError("recovery refuses externally modified content")
        backup_name = item["backup"]
        if Path(backup_name).name != backup_name:
            raise ValueError("invalid backup name")
        backup_path = journal / backup_name
        if backup_path.is_symlink():
            raise ValueError("symlink backup refused")
        backup = read_bounded(backup_path)
        if hashlib.sha256(backup).hexdigest() != item["before"]:
            raise ValueError("backup hash mismatch")
        verified.append((path, backup))
    for path, backup in verified:
        _write_atomic(path, backup)
    (journal / "recovered").write_text("original contents restored\n")
