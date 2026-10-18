"""JSON analysis cache keyed by content, parser, rules, config and dependency closure."""

from __future__ import annotations

import ast
import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.frontend.discovery import (
    Limits,
    ParseFailure,
    discover,
    parse,
    read_bounded,
    read_source,
)
from pp_pytrace.reporting.models import Diagnostic, Evidence, Location
from pp_pytrace.rules.registry import Config
from pp_pytrace.semantics.symbols import dependencies

ENGINE_VERSION = "pytrace-1.0.0"


@dataclass(frozen=True)
class Result:
    diagnostics: tuple[Diagnostic, ...]
    invalidated: tuple[str, ...]
    files: int
    iterations: int
    parse_failures: int
    cache_hits: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "invalidated": self.invalidated,
            "files": self.files,
            "iterations": self.iterations,
            "parse_failures": self.parse_failures,
            "cache_hits": self.cache_hits,
        }


def _diagnostic(value: dict[str, Any]) -> Diagnostic:
    return Diagnostic(
        value["rule_id"],
        value["severity"],
        value["confidence"],
        value["path"],
        Location(**value["location"]),
        Location(**value["sink_location"]),
        tuple(Evidence(**item) for item in value["evidence"]),
        value["message"],
        value["coverage"],
    )


def analyze(
    root: Path,
    cache: Path | None = None,
    config: Config = Config(),
    limits: Limits = Limits(),
    excludes: tuple[str, ...] = (".venv/*", ".git/*", "__pycache__/*"),
) -> Result:
    root = root.resolve(strict=True)
    base = root.parent if root.is_file() else root
    files = discover(root, excludes, limits)
    previous: dict[str, Any] = {}
    if cache and cache.exists():
        try:
            data = json.loads(read_bounded(cache, 64 * 1024 * 1024).decode("utf-8"))
            if data.get("version") == ENGINE_VERSION and data.get("root") == str(root):
                previous = data["entries"]
        except (ValueError, KeyError, TypeError):
            previous = {}
    sources: dict[str, str] = {}
    hashes: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    errors: dict[str, ParseFailure] = {}
    deps: dict[str, list[str]] = {}
    package_root = Path(__file__).parent
    engine_files = [
        "analysis/engine.py",
        "analysis/lattice.py",
        "cfg/blocks.py",
        "semantics/symbols.py",
        "rules/registry.py",
        "frontend/discovery.py",
        "frontend/parser_worker.py",
    ]
    engine_hash = hashlib.sha256(
        b"".join((package_root / name).read_bytes() for name in engine_files)
    ).hexdigest()
    parser_key = (
        engine_hash
        + ":"
        + platform.python_version()
        + ":"
        + hashlib.sha256(json.dumps(asdict(limits), sort_keys=True).encode()).hexdigest()
    )
    for path in files:
        name = path.relative_to(base).as_posix()
        try:
            source = read_source(path, limits)
            sources[name] = source
            hashes[name] = hashlib.sha256(source.encode()).hexdigest()
            old = previous.get(name, {})
            if old.get("content") == hashes[name] and old.get("parser") == parser_key:
                deps[name] = old["dependencies"]
            else:
                trees[name] = parse(source, name, limits)
                deps[name] = sorted(dependencies(trees[name]))
        except ParseFailure as exc:
            errors[name] = exc
            stat = path.stat()
            # Rejected files never hit the success cache; identity is bounded metadata.
            hashes[name] = hashlib.sha256(
                f"rejected:{stat.st_size}:{stat.st_mtime_ns}".encode()
            ).hexdigest()
            deps[name] = []
    modules = {name.removesuffix(".py").replace("/", "."): name for name in hashes}
    modules.update(
        {
            key.removesuffix(".__init__"): value
            for key, value in list(modules.items())
            if key.endswith(".__init__")
        }
    )
    graph: dict[str, set[str]] = {}
    for name, imports in deps.items():
        package = name.removesuffix(".py").replace("/", ".").split(".")[:-1]
        graph[name] = set()
        for item in imports:
            if item.startswith("."):
                level = len(item) - len(item.lstrip("."))
                item = ".".join(package[: len(package) - level + 1] + [item.lstrip(".")]).rstrip(
                    "."
                )
            components = item.split(".")
            for length in range(1, len(components) + 1):
                dependency = modules.get(".".join(components[:length]))
                if dependency:
                    graph[name].add(dependency)
    entries: dict[str, Any] = {}
    invalidated: list[str] = []
    findings: list[Diagnostic] = []
    iterations = 0
    failures = 0
    hits = 0
    for name in sorted(hashes):
        closure: set[str] = set()
        pending = [name]
        while pending:
            dependency = pending.pop()
            if dependency not in closure:
                closure.add(dependency)
                pending.extend(sorted(graph[dependency]))
        key = hashlib.sha256(
            json.dumps(
                [
                    ENGINE_VERSION,
                    parser_key,
                    config.fingerprint,
                    [(item, hashes[item]) for item in sorted(closure)],
                    sorted(modules),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        old = previous.get(name, {})
        if old.get("key") == key and name not in errors:
            try:
                diagnostics = [_diagnostic(item) for item in old["diagnostics"]]
                hits += 1
            except (KeyError, TypeError, ValueError):
                old = {}
        if old.get("key") != key or name in errors:
            invalidated.append(name)
            if name in errors:
                failure = errors[name]
                loc = Location(failure.line, failure.column, failure.line, failure.column + 1)
                diagnostics = [
                    Diagnostic(
                        "PT901",
                        "error",
                        "high",
                        name,
                        loc,
                        loc,
                        (Evidence(failure.line, str(failure)),),
                        str(failure),
                        "unparsed",
                    )
                ]
                failures += 1
            else:
                tree = trees.get(name) or parse(sources[name], name, limits)
                result = Analyzer(sources[name], name, config).run(tree)
                diagnostics = list(result.diagnostics)
                iterations += result.iterations
        entries[name] = {
            "key": key,
            "content": hashes[name],
            "parser": parser_key,
            "dependencies": deps[name],
            "diagnostics": [item.to_dict() for item in diagnostics],
        }
        findings.extend(diagnostics)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_name(cache.name + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": ENGINE_VERSION,
                    "root": str(root),
                    "entries": entries,
                },
                indent=2,
            )
            + "\n"
        )
        temporary.replace(cache)
    return Result(tuple(findings), tuple(invalidated), len(files), iterations, failures, hits)
