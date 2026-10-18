"""Lexical binding collection without importing the target or configuration."""

from __future__ import annotations

import ast

from pp_pytrace.analysis.lattice import Environment, Value


class Locals(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.globals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.update(alias.asname or alias.name for alias in node.names)

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_ListComp(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
    ) -> None:
        pass  # comprehension variables occupy their own lexical scope

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp


def imported(node: ast.Import | ast.ImportFrom) -> Environment:
    if isinstance(node, ast.Import):
        return {
            alias.asname or alias.name.split(".")[0]: Value(
                targets=frozenset([alias.name if alias.asname else alias.name.split(".")[0]])
            )
            for alias in node.names
        }
    prefix = "." * node.level + (node.module or "")
    return {
        alias.asname or alias.name: Value(targets=frozenset([prefix + "." + alias.name]))
        for alias in node.names
        if alias.name != "*"
    }


def dependencies(tree: ast.Module) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            names.add(prefix)
            names.update(
                prefix + "." + alias.name if node.module else prefix + alias.name
                for alias in node.names
            )
    return frozenset(names)
