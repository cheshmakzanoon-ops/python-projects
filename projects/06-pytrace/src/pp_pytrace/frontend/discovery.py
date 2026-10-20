"""Caller-selected discovery, source decoding and bounded subprocess parsing."""

from __future__ import annotations

import ast
import io
import json
import stat
import subprocess
import sys
import time
import tokenize
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 512_000
    max_nodes: int = 80_000
    max_files: int = 10_000
    timeout_seconds: float = 5
    memory_bytes: int = 384 * 1024 * 1024


class ParseFailure(ValueError):
    def __init__(self, message: str, line: int = 1, column: int = 1) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


def read_bounded(path: Path, max_bytes: int = Limits().max_bytes) -> bytes:
    """Bound before allocation and on read, including a file-growth race."""
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ParseFailure("source must be a regular file")
    if metadata.st_size > max_bytes:
        raise ParseFailure("source byte limit exceeded")
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ParseFailure("source byte limit exceeded")
    return data


def decode_source(data: bytes) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        return data.decode(encoding)
    except (SyntaxError, UnicodeError) as exc:
        raise ParseFailure(str(exc)) from exc


def read_source(path: Path, limits: Limits = Limits()) -> str:
    return decode_source(read_bounded(path, limits.max_bytes))


def guard_output(output: Path, sources: list[Path]) -> None:
    """Refuse an output that aliases selected source, including hard links.

    Path spelling alone is insufficient: callers may select a symlink or a
    second hard link to the source as a report/cache destination. This preflight
    protects ordinary local use; it does not lock out concurrent filesystem edits.
    """
    resolved = output.resolve()
    for source in sources:
        if resolved == source.resolve() or (
            output.exists() and source.exists() and output.samefile(source)
        ):
            raise ValueError("output must not overwrite selected source")


def discover(
    root: Path,
    excludes: tuple[str, ...] = (".venv/*", ".git/*", "__pycache__/*"),
    limits: Limits = Limits(),
) -> list[Path]:
    if root.is_symlink():
        raise ValueError("source symlink/path escape refused")
    root = root.resolve(strict=True)
    if not root.is_file() and not root.is_dir():
        raise ValueError("source root must be a regular file or directory")
    candidates = [root] if root.is_file() else root.rglob("*.py")
    result = []
    for path in candidates:
        relative = path.name if root.is_file() else path.relative_to(root).as_posix()
        if any(
            fnmatch(relative, pattern)
            or any(
                fnmatch(part + "/", pattern)
                for part in path.relative_to(root.parent if root.is_file() else root).parts
            )
            for pattern in excludes
        ):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(
            root.parent if root.is_file() else root
        ):
            raise ValueError(f"source symlink/path escape refused: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"source must be a regular file: {relative}")
        result.append(path)
        if len(result) > limits.max_files:
            raise ValueError("source file count limit exceeded")
    return sorted(result)


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and "_type" in value:
        node_type = getattr(ast, value["_type"], None)
        if not isinstance(node_type, type) or not issubclass(node_type, ast.AST):
            raise ParseFailure("invalid AST response")
        fields = {key: _decode(item) for key, item in value.items() if key != "_type"}
        return node_type(**fields)
    if isinstance(value, dict) and "_constant" in value:
        if value["_constant"] == "bytes":
            return bytes.fromhex(value["hex"])
        if value["_constant"] == "complex":
            return complex(value["real"], value["imag"])
        if value["_constant"] == "ellipsis":
            return Ellipsis
        raise ParseFailure("unsupported constant response")
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def parse(source: str, filename: str = "<source>", limits: Limits = Limits()) -> ast.Module:
    if len(source.encode()) > limits.max_bytes:
        raise ParseFailure("source byte limit exceeded")
    worker = Path(__file__).with_name("parser_worker.py")
    request = {
        "source": source,
        "filename": filename,
        "memory_bytes": limits.memory_bytes,
        "max_nodes": limits.max_nodes,
    }
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(worker)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=limits.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseFailure("parser timeout exceeded") from exc
    if time.monotonic() - started > limits.timeout_seconds:
        raise ParseFailure("parser timeout exceeded (including process startup)")
    if completed.returncode != 0:
        raise ParseFailure(f"bounded parser failed (exit {completed.returncode})")
    if len(completed.stdout) > 32_000_000:
        raise ParseFailure("parser response limit exceeded")
    response = json.loads(completed.stdout)
    if "error" in response:
        raise ParseFailure(response["error"], response["line"], response["column"])
    result = _decode(response["tree"])
    if not isinstance(result, ast.Module):
        raise ParseFailure("invalid parser root")
    return result
