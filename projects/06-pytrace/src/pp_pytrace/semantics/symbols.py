"""Lexical binding collection without importing the target or configuration."""

from __future__ import annotations

import ast

from pp_pytrace.analysis.lattice import Environment, Value


def definition_expressions(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda,
) -> list[ast.expr]:
    """Expressions evaluated in the enclosing scope, excluding annotations."""
    if isinstance(node, ast.ClassDef):
        return [*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords)]
    decorators = [] if isinstance(node, ast.Lambda) else node.decorator_list
    return [
        *decorators,
        *node.args.defaults,
        *(item for item in node.args.kw_defaults if item is not None),
    ]


def parameters(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> list[str]:
    return [
        argument.arg
        for argument in (
            node.args.posonlyargs
            + node.args.args
            + node.args.kwonlyargs
            + ([node.args.vararg] if node.args.vararg else [])
            + ([node.args.kwarg] if node.args.kwarg else [])
        )
    ]


def pattern_bindings(pattern: ast.pattern) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def named_expression_bindings(node: ast.AST) -> set[str]:
    class Bindings(ast.NodeVisitor):
        names: set[str]

        def __init__(self) -> None:
            self.names = set()

        def visit_NamedExpr(self, value: ast.NamedExpr) -> None:
            if isinstance(value.target, ast.Name):
                self.names.add(value.target.id)
            self.visit(value.value)

        def visit_Lambda(self, value: ast.Lambda) -> None:
            for expression in definition_expressions(value):
                self.visit(expression)

    visitor = Bindings()
    visitor.visit(node)
    return visitor.names


class Locals(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()

    @property
    def local_bindings(self) -> set[str]:
        return self.names - self.globals - self.nonlocals

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
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)
        for expression in definition_expressions(node):
            self.visit(expression)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)
        for expression in definition_expressions(node):
            self.visit(expression)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)
        for expression in definition_expressions(node):
            self.visit(expression)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in definition_expressions(node):
            self.visit(expression)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_match_case(self, node: ast.match_case) -> None:
        self.names.update(pattern_bindings(node.pattern))
        self.generic_visit(node)

    def visit_ListComp(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
    ) -> None:
        # Iteration targets occupy the comprehension scope; walrus targets bind
        # in the enclosing function, as Python's symbol-table pass specifies.
        self.names.update(named_expression_bindings(node))

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
