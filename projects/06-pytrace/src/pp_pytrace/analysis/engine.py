"""Original forward may-analysis over a finite product lattice and CFG worklist."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import deque
from dataclasses import dataclass
from functools import reduce

from pp_pytrace.analysis.lattice import (
    BOTTOM,
    SHELL,
    SQL,
    UNKNOWN,
    Environment,
    Value,
    environment_key,
    join_environments,
)
from pp_pytrace.cfg.blocks import build
from pp_pytrace.reporting.models import Diagnostic, Evidence, location
from pp_pytrace.rules.registry import Config
from pp_pytrace.semantics.symbols import Locals, imported


@dataclass(frozen=True)
class Analysis:
    diagnostics: tuple[Diagnostic, ...]
    iterations: int
    blocks: int


class Analyzer:
    def __init__(self, source: str, path: str, config: Config = Config()) -> None:
        self.source = source
        self.path = path
        self.config = config
        self.findings: dict[str, Diagnostic] = {}
        self.iterations = 0
        self.blocks = 0
        self.async_context = False
        self.suppressions: dict[int, set[str]] = {}
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.COMMENT:
                continue
            line, text = token.start[0], token.string
            match = re.search(r"#\s*pytrace:\s*ignore\[([A-Z0-9, ]+)\]", text)
            if match:
                self.suppressions[line] = set(match[1].replace(" ", "").split(","))

    def emit(
        self, rule: str, node: ast.AST, message: str, value: Value = BOTTOM, uncertain: bool = False
    ) -> None:
        loc = location(node, self.source)
        if rule in self.suppressions.get(loc.line, set()):
            return
        origins = tuple(
            Evidence(
                line, "configured untrusted source" if value.taint else "value enters modeled flow"
            )
            for line in sorted(value.origins)
        )
        evidence = origins + (Evidence(loc.line, message),)
        item = Diagnostic(
            rule,
            "warning" if rule == "PT900" else "error",
            "uncertain" if uncertain else "high",
            self.path,
            loc,
            loc,
            evidence,
            message,
            "partial" if uncertain or rule == "PT900" else "modeled",
        )
        previous = self.findings.get(item.identifier)
        if (
            previous is None
            or len(previous.evidence) < len(item.evidence)
            or (previous.confidence == "uncertain" and item.confidence == "high")
        ):
            self.findings[item.identifier] = item

    def expression(self, node: ast.AST | None, env: Environment) -> Value:
        if node is None:
            return BOTTOM
        if isinstance(node, ast.Constant):
            return BOTTOM
        if isinstance(node, ast.Name):
            return env.get(node.id, UNKNOWN)
        if isinstance(node, ast.Attribute):
            base = self.expression(node.value, env)
            targets = frozenset(target + "." + node.attr for target in base.targets)
            if node.attr in self.config.sql_methods:
                targets = targets | frozenset(["__sql__." + node.attr])
            return Value(base.taint, base.built, base.unknown, targets, base.origins)
        if isinstance(node, ast.Call):
            target = self.expression(node.func, env)
            arguments = [self.expression(arg, env) for arg in node.args]
            keywords = [self.expression(kw.value, env) for kw in node.keywords]
            values = arguments + keywords
            combined = reduce(Value.join, values, BOTTOM)
            names = target.targets
            if names & set(self.config.sources):
                return Value(
                    SHELL | SQL,
                    unknown=target.unknown or len(names) != 1,
                    origins=frozenset([node.lineno]),
                )
            shell = names & set(self.config.shell_sinks)
            if shell:
                shell_kw = next((kw.value for kw in node.keywords if kw.arg == "shell"), None)
                direct = "os.system" in shell
                enabled = direct or isinstance(shell_kw, ast.Constant) and bool(shell_kw.value)
                uncertain_shell = (
                    (shell_kw is not None and not isinstance(shell_kw, ast.Constant))
                    or shell_kw is None
                    and any(kw.arg is None for kw in node.keywords)
                )
                command = (
                    arguments[0]
                    if arguments
                    else next(
                        (
                            value
                            for kw, value in zip(node.keywords, keywords, strict=True)
                            if kw.arg in ("args", "command")
                        ),
                        UNKNOWN,
                    )
                )
                if enabled or uncertain_shell:
                    if command.taint & SHELL:
                        self.emit(
                            "PT001",
                            node,
                            "Untrusted value flows to a shell-enabled process",
                            command,
                            uncertain_shell or target.unknown or command.unknown,
                        )
                    elif command.unknown:
                        self.emit(
                            "PT001",
                            node,
                            "Unknown value may flow to a shell-enabled process",
                            command,
                            True,
                        )
            sql_call = any(
                name == "__sql__." + method for name in names for method in self.config.sql_methods
            )
            if sql_call:
                query = (
                    arguments[0]
                    if arguments
                    else next(
                        (
                            value
                            for kw, value in zip(node.keywords, keywords, strict=True)
                            if kw.arg in ("query", "sql", "operation")
                        ),
                        UNKNOWN,
                    )
                )
                if query.built or query.taint & SQL:
                    self.emit(
                        "PT002",
                        node,
                        "String-built or untrusted SQL flows to an execution method",
                        query,
                        query.unknown,
                    )
                elif query.unknown:
                    self.emit(
                        "PT002", node, "Unknown SQL text reaches an execution method", query, True
                    )
            if self.async_context and names & set(self.config.blocking):
                self.emit(
                    "PT003",
                    node,
                    "Configured synchronous blocking call inside async function",
                    target,
                    target.unknown,
                )
            unambiguous = len(names) == 1 and not target.unknown
            if unambiguous and names & set(self.config.shell_sanitizers):
                return Value(
                    combined.taint & ~SHELL,
                    combined.built,
                    combined.unknown,
                    origins=combined.origins,
                )
            if unambiguous and names & set(self.config.sql_sanitizers):
                return Value(
                    combined.taint & ~SQL, False, combined.unknown, origins=combined.origins
                )
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "join"):
                base = target.join(combined)
                return Value(base.taint, True, base.unknown, origins=base.origins)
            if (
                sql_call
                or names & set(self.config.shell_sinks)
                or names & set(self.config.blocking)
            ):
                return UNKNOWN
            if names:
                self.emit(
                    "PT900", node, "Call return value has no configured summary", uncertain=True
                )
            else:
                self.emit(
                    "PT900",
                    node,
                    "Unresolved call target; returned data is unknown",
                    uncertain=True,
                )
            return combined.join(UNKNOWN)
        if isinstance(node, (ast.BinOp, ast.JoinedStr)):
            children = list(ast.iter_child_nodes(node))
            combined = reduce(
                Value.join,
                (self.expression(child, env) for child in children if isinstance(child, ast.expr)),
                BOTTOM,
            )
            return Value(combined.taint, True, combined.unknown, origins=combined.origins)
        if isinstance(node, ast.NamedExpr):
            value = self.expression(node.value, env)
            self.bind(node.target, value, env)
            return value
        if isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)
        ):
            self.emit(
                "PT900",
                node,
                "Comprehension/lambda has a nested scope; effects and data are unknown",
                uncertain=True,
            )
            return UNKNOWN
        if isinstance(node, ast.Subscript):
            base = self.expression(node.value, env)
            return base.join(UNKNOWN)
        if isinstance(node, ast.IfExp):
            self.expression(node.test, env)
            left, right = dict(env), dict(env)
            value = self.expression(node.body, left).join(self.expression(node.orelse, right))
            env.update(join_environments(left, right))
            return value
        if isinstance(node, ast.BoolOp):
            combined = BOTTOM
            exits: Environment | None = None
            for operand in node.values:
                combined = combined.join(self.expression(operand, env))
                # Any operand can short circuit; later writes are only conditional.
                exits = dict(env) if exits is None else join_environments(exits, env)
            if exits is not None:
                env.update(exits)
            return combined
        return reduce(
            Value.join,
            (
                self.expression(child, env)
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.expr)
            ),
            BOTTOM,
        )

    def bind(self, target: ast.AST, value: Value, env: Environment) -> None:
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self.bind(item, value.join(UNKNOWN), env)
        else:
            self.emit(
                "PT900",
                target,
                "Heap mutation is outside intraprocedural name-state model",
                uncertain=True,
            )

    def transfer(self, node: ast.stmt | None, incoming: Environment) -> Environment:
        env = dict(incoming)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            env.update(imported(node))
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                self.emit(
                    "PT900", node, "Wildcard imports make local bindings uncertain", uncertain=True
                )
                for name in env:
                    env[name] = env[name].join(UNKNOWN)
        elif isinstance(node, ast.Assign):
            value = self.expression(node.value, env)
            for target in node.targets:
                self.bind(target, value, env)
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.bind(node.target, self.expression(node.value, env), env)
        elif isinstance(node, ast.AugAssign):
            value = self.expression(node.target, env).join(self.expression(node.value, env))
            self.bind(
                node.target, Value(value.taint, True, value.unknown, origins=value.origins), env
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            env[node.name] = UNKNOWN
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            self.bind(node.target, self.expression(node.iter, env).join(UNKNOWN), env)
        elif isinstance(node, (ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.Match)):
            self.emit(
                "PT900",
                node,
                "Exception/context/match edges are conservative; binding and exit effects are unsupported",
                uncertain=True,
            )
            for key in env:
                env[key] = env[key].join(UNKNOWN)
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    self.expression(item.context_expr, env)
                    if item.optional_vars:
                        self.bind(item.optional_vars, UNKNOWN, env)
            elif isinstance(node, ast.Match):
                self.expression(node.subject, env)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                self.bind(target, UNKNOWN, env)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.emit(
                "PT900",
                node,
                "Global/nonlocal mutation is outside intraprocedural model",
                uncertain=True,
            )
        elif node:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    self.expression(child, env)
        return env

    def flow(self, body: list[ast.stmt], initial: Environment) -> Environment:
        graph = build(body)
        self.blocks += len(graph.blocks)
        states = {graph.entry: dict(initial)}
        queue = deque([graph.entry])
        pending = {graph.entry}
        while queue:
            index = queue.popleft()
            pending.remove(index)
            self.iterations += 1
            output = self.transfer(graph.blocks[index].node, states[index])
            for next_index in graph.blocks[index].successors:
                previous = states.get(next_index)
                merged = output if previous is None else join_environments(previous, output)
                changed = previous is None or environment_key(previous) != environment_key(merged)
                states[next_index] = merged
                if changed and next_index not in pending:
                    queue.append(next_index)
                    pending.add(next_index)
        return states.get(0, initial)

    def run(self, tree: ast.Module) -> Analysis:
        builtins = {
            name: Value(targets=frozenset([name]))
            for name in ("input", "str", "int", "exec", "eval", "__import__")
        }
        canonical_names = (
            self.config.sources
            + self.config.shell_sanitizers
            + self.config.sql_sanitizers
            + self.config.shell_sinks
            + self.config.blocking
        )
        builtins.update(
            {name: Value(targets=frozenset([name])) for name in canonical_names if "." not in name}
        )
        global_env = self.flow(tree.body, builtins)
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        functions = [
            node for node in parents if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        locals_by_node: dict[ast.AST, Locals] = {}
        for node in functions:
            local = Locals()
            for statement in node.body:
                local.visit(statement)
            locals_by_node[node] = local
        for node in functions:
            local = locals_by_node[node]
            env = dict(global_env)
            enclosing = parents.get(node)
            nested = False
            while enclosing is not None:
                if isinstance(enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nested = True
                    captured = locals_by_node[enclosing]
                    for name in captured.names:
                        env[name] = UNKNOWN
                    for argument in (
                        enclosing.args.posonlyargs + enclosing.args.args + enclosing.args.kwonlyargs
                    ):
                        env[argument.arg] = UNKNOWN
                enclosing = parents.get(enclosing)
            for name in local.names - local.globals:
                env[name] = UNKNOWN
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            for arg in (
                args
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            ):
                env[arg.arg] = UNKNOWN
            self.async_context = isinstance(node, ast.AsyncFunctionDef)
            self.flow(node.body, env)
            if nested:
                self.emit(
                    "PT900",
                    node,
                    "Nested function closures use unknown captured locals",
                    uncertain=True,
                )
        return Analysis(
            tuple(
                sorted(
                    self.findings.values(),
                    key=lambda item: (
                        item.path,
                        item.location.line,
                        item.location.column,
                        item.rule_id,
                    ),
                )
            ),
            self.iterations,
            self.blocks,
        )
