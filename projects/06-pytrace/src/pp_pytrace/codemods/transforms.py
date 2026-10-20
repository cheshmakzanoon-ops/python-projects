"""Conservative LibCST transformations with qualified-name and scope metadata."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedNameProvider,
    QualifiedNameSource,
    ScopeProvider,
)

from pp_pytrace.frontend.discovery import parse
from pp_pytrace.reporting.models import SourceMap


@dataclass(frozen=True)
class MigrationManifest:
    callable: str
    api_version: str
    api_sha256: str
    old_keyword: str
    new_keyword: str

    @classmethod
    def trusted(cls) -> MigrationManifest:
        digest = "da1f8dfe03773df46e45a72a59b444d7b61dcefdc8f8d380fe67814ca3c44ddb"
        return cls("pp_pytrace.trusted_api.deliver", "1", digest, "timeout", "deadline")

    def validate(self) -> None:
        actual = hashlib.sha256(
            Path(__file__).parents[1].joinpath("trusted_api.py").read_bytes()
        ).hexdigest()
        if self != self.trusted() or actual != self.api_sha256:
            raise ValueError("unsupported API manifest/version/hash/preconditions")


@dataclass(frozen=True)
class Rewrite:
    before: str
    after: str
    changes: tuple[str, ...]
    abstentions: tuple[str, ...]


class ConservativeTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (
        QualifiedNameProvider,
        ScopeProvider,
        PositionProvider,
        ParentNodeProvider,
    )

    def __init__(
        self, source: str, forbidden: set[tuple[int, int]], manifest: MigrationManifest
    ) -> None:
        self.source = source
        self.forbidden = forbidden
        self.manifest = manifest
        self.changes: list[str] = []
        self.abstentions: list[str] = []
        self.module = cst.Module([])

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        names = self.get_metadata(QualifiedNameProvider, original.func, set())
        # ScopeProvider participation makes missing/unsupported scope an abstention.
        scope = self.get_metadata(ScopeProvider, original, None)
        pos = self.get_metadata(PositionProvider, original).start
        label = f"{pos.line}:{pos.column + 1}"
        is_str = isinstance(original.func, cst.Name) and original.func.value == "str"
        if is_str:
            if (
                scope is None
                or len(names) != 1
                or not any(
                    name.name == "builtins.str" and name.source is QualifiedNameSource.BUILTIN
                    for name in names
                )
            ):
                self.abstentions.append(label + " shadowed or ambiguous str binding")
                return updated
            if (
                len(updated.args) != 1
                or updated.args[0].keyword is not None
                or updated.args[0].star
                or not isinstance(updated.args[0].value, cst.SimpleString)
            ):
                self.abstentions.append(label + " constructor requires one explicit text literal")
                return updated
            literal = updated.args[0].value
            if not isinstance(literal.evaluated_value, str):
                self.abstentions.append(label + " bytes literal is not eligible")
                return updated
            if (pos.line, pos.column + 1) in self.forbidden:
                self.abstentions.append(label + " replacement would create a docstring")
                return updated
            if "#" in self.module.code_for_node(original):
                self.abstentions.append(label + " embedded comments/ambiguous trivia")
                return updated
            self.changes.append(label + " redundant literal constructor")
            return literal.with_changes(
                lpar=tuple(updated.lpar) + tuple(literal.lpar),
                rpar=tuple(literal.rpar) + tuple(updated.rpar),
            )
        canonical = self.manifest.callable
        if any(name.name == canonical for name in names):
            if (
                scope is None
                or len(names) != 1
                or not all(name.source is QualifiedNameSource.IMPORT for name in names)
            ):
                self.abstentions.append(label + " ambiguous API binding")
                return updated
            keywords = [arg.keyword.value for arg in original.args if arg.keyword]
            if (
                keywords.count(self.manifest.old_keyword) != 1
                or self.manifest.new_keyword in keywords
                or any(arg.star for arg in original.args)
            ):
                self.abstentions.append(
                    label + " API requires one old keyword, no new keyword or unpacking"
                )
                return updated
            self.changes.append(label + " trusted keyword-only API migration")
            return updated.with_changes(
                args=[
                    arg.with_changes(keyword=cst.Name(self.manifest.new_keyword))
                    if arg.keyword and arg.keyword.value == self.manifest.old_keyword
                    else arg
                    for arg in updated.args
                ]
            )
        return updated


def rewrite(source: str, manifest: MigrationManifest | None = None) -> Rewrite:
    selected = manifest or MigrationManifest.trusted()
    selected.validate()
    tree = parse(source)
    if any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        for node in ast.walk(tree)
    ):
        # QualifiedNameProvider cannot enumerate names introduced by a star import.
        return Rewrite(source, source, (), ("wildcard imports make bindings uncertain",))
    forbidden = set()
    locations = SourceMap(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
        ):
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
                loc = locations.location(first.value)
                forbidden.add((loc.line, loc.column))
    try:
        module = cst.parse_module(source)
        transformer = ConservativeTransformer(source, forbidden, selected)
        result = MetadataWrapper(module).visit(transformer)
    except (cst.ParserSyntaxError, cst.CSTValidationError, NotImplementedError) as exc:
        return Rewrite(source, source, (), ("unsupported syntax/metadata: " + str(exc),))
    after = result.code
    parse(after)  # bounded parse/compilation shape check, never execute target
    return Rewrite(source, after, tuple(transformer.changes), tuple(transformer.abstentions))
