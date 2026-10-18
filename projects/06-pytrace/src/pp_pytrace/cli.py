"""Safe CLI: analysis never imports, configures or executes target programs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pp_pytrace.cache import analyze
from pp_pytrace.codemods.plan import apply, create_plan, load_plan, patch, recover
from pp_pytrace.frontend.discovery import ParseFailure, read_bounded
from pp_pytrace.reporting.sarif import sarif, validate
from pp_pytrace.rules.registry import Config
from pp_pytrace.workloads import benchmark, clean_demo, demo


def _emit(data: Any, output: Path | None) -> None:
    text = data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    else:
        print(text, end="" if text.endswith("\n") else "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pytrace", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    analysis = commands.add_parser(
        "analyze", help="analyze selected Python source without execution"
    )
    analysis.add_argument("root", type=Path)
    analysis.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    analysis.add_argument("--output", type=Path)
    analysis.add_argument("--cache", type=Path)
    analysis.add_argument(
        "--config", type=Path, help="bounded declarative JSON call summaries; never Python"
    )
    analysis.add_argument("--fail-on-findings", action="store_true")
    explain = commands.add_parser("explain")
    explain.add_argument("root", type=Path)
    explain.add_argument("identifier")
    preview = commands.add_parser("diff")
    preview.add_argument("root", type=Path)
    preview.add_argument("files", nargs="+")
    preview.add_argument("--plan", type=Path)
    preview.add_argument("--output", type=Path)
    applying = commands.add_parser("apply")
    applying.add_argument("plan", type=Path)
    applying.add_argument(
        "--root", type=Path, required=True, help="independently selected authorized source root"
    )
    applying.add_argument("--journal", type=Path, required=True)
    recovery = commands.add_parser("recover")
    recovery.add_argument("journal", type=Path)
    recovery.add_argument("--root", type=Path, required=True)
    inspect = commands.add_parser("cache")
    inspect.add_argument("action", choices=["inspect"])
    inspect.add_argument("path", type=Path)
    for name in ("demo", "benchmark", "clean-demo"):
        child = commands.add_parser(name)
        child.add_argument("--output", type=Path, required=True)
        if name != "clean-demo":
            child.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            child.add_argument("--profile", choices=["ci", "standard"], default="ci")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "analyze":
            config = Config()
            if args.config:
                if args.config.stat().st_size > 32_000:
                    raise ValueError("configuration byte limit exceeded")
                settings = json.loads(read_bounded(args.config, 32_000).decode("utf-8"))
                if not isinstance(settings, dict) or any(
                    key not in Config.__dataclass_fields__
                    or not isinstance(values, list)
                    or len(values) > 100
                    or not all(isinstance(value, str) and len(value) <= 200 for value in values)
                    for key, values in settings.items()
                ):
                    raise ValueError("invalid declarative configuration")
                config = Config(**{key: tuple(values) for key, values in settings.items()})
            result = analyze(args.root, args.cache, config)
            data: Any
            if args.format == "sarif":
                data = sarif(result.diagnostics)
                validate(data)
            elif args.format == "json":
                data = result.to_dict()
            else:
                data = (
                    "\n".join(
                        f"{item.path}:{item.location.line}:{item.location.column} {item.rule_id} [{item.confidence}] {item.message} ({item.identifier})"
                        for item in result.diagnostics
                    )
                    + "\n"
                )
            _emit(data, args.output)
            return 1 if result.parse_failures or args.fail_on_findings and result.diagnostics else 0
        if args.command == "explain":
            result = analyze(args.root)
            matching = [
                item.to_dict() for item in result.diagnostics if item.identifier == args.identifier
            ]
            if not matching:
                raise ValueError("diagnostic identifier not found")
            _emit(matching[0], None)
        elif args.command == "diff":
            plan = create_plan(args.root, args.files)
            _emit(patch(plan), args.output)
            if args.plan:
                _emit(plan.to_dict(), args.plan)
            for message in plan.abstentions:
                print("abstain: " + message, file=sys.stderr)
        elif args.command == "apply":
            plan = load_plan(args.plan)
            if Path(plan.root).resolve() != args.root.resolve(strict=True):
                raise ValueError("plan root does not match authorized --root")
            apply(plan, args.journal)
            _emit({"applied_files": len(plan.edits), "journal": str(args.journal)}, None)
        elif args.command == "recover":
            data = json.loads(read_bounded(args.journal / "plan.json", 4_000_000).decode("utf-8"))
            if Path(data["root"]).resolve() != args.root.resolve(strict=True):
                raise ValueError("journal root does not match authorized --root")
            recover(args.journal)
        elif args.command == "cache":
            data = json.loads(read_bounded(args.path, 64 * 1024 * 1024).decode("utf-8"))
            _emit(
                {
                    "version": data.get("version"),
                    "root": data.get("root"),
                    "entries": [
                        {
                            "path": path,
                            "dependencies": record["dependencies"],
                            "content_sha256": record["content"],
                        }
                        for path, record in sorted(data["entries"].items())
                    ],
                },
                None,
            )
        elif args.command == "demo":
            report = demo(args.output, args.seed)
            _emit(report, None)
            return 0 if report["status"] == "passed" else 1
        elif args.command == "benchmark":
            report = benchmark(args.output, args.profile, args.seed)
            _emit(report, None)
            return 0 if report["status"] == "passed" else 1
        elif args.command == "clean-demo":
            clean_demo(args.output)
        return 0
    except (ValueError, OSError, KeyError, TypeError, ParseFailure) as exc:
        print(f"pytrace: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
