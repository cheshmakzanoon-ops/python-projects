"""CLI over the same public solver/verifier/replanning APIs used by tests."""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from pp_routecraft.benchmark import run_benchmark
from pp_routecraft.construction.insertion import construct
from pp_routecraft.domain.instance import Plan, SearchBudget
from pp_routecraft.fixtures import island, new_request, tiny
from pp_routecraft.reference.exhaustive import exhaustive
from pp_routecraft.replanning.rolling import prepare_replan
from pp_routecraft.reporting.report import (
    clean_output,
    output_directory,
    provenance,
    render,
    save_result,
    write_json,
)
from pp_routecraft.reporting.serialization import instance_dict, read_instance, read_plan
from pp_routecraft.search.solver import solve
from pp_routecraft.validation.verifier import verify


def demo(output: Path, seed: int) -> None:
    instance = island(25, seed)
    baseline = construct(instance, regret=False)
    if baseline is None:
        raise RuntimeError("demo baseline did not find a feasible plan")
    result = solve(instance, SearchBudget(150), seed=seed, initial=baseline)
    if result.plan is None:
        raise RuntimeError("demo search did not retain its feasible incumbent")
    save_result(instance, result, output)
    nonempty = next(r for r in result.plan.routes if r.stops)
    corrupt = Plan(
        (replace(nonempty, stops=nonempty.stops + nonempty.stops[:1]),)
        + tuple(r for r in result.plan.routes if r is not nonempty),
        result.plan.objective,
    )
    rejected = verify(instance, corrupt)
    if rejected.valid:
        raise RuntimeError("independent verifier accepted a duplicated delivery")
    updated = new_request(instance, result.plan)
    replanned = solve(updated, SearchBudget(100), seed=seed)
    if replanned.plan is None:
        raise RuntimeError("new request could not be planned")
    if not verify(updated, replanned.plan).valid:
        raise RuntimeError("new plan failed independent verification")
    write_json(output / "replanned-instance.json", instance_dict(updated))
    write_json(output / "replanned-plan.json", asdict(replanned.plan))
    render(updated, replanned.plan, output, prefix="replanned-")
    project = Path(__file__).resolve().parents[2]
    write_json(
        output / "demo.json",
        {
            "schema_version": 1,
            "seed": seed,
            **provenance(project),
            "baseline_objective": baseline.objective,
            "improved_objective": result.plan.objective,
            "rejected_plan_diagnostics": rejected.errors,
            "replanning_objective": replanned.plan.objective,
            "verified": True,
            "coordinates": "synthetic visual aids, not roads",
            "limitations": "heuristic optimality gap unknown; no reloading or transfers",
        },
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "objective": result.plan.objective,
                "replanned": replanned.plan.objective,
                "output": str(output),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="routecraft",
        description="Original capacitated directed routing with independently verified schedules",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "demo",
        "benchmark",
        "clean-demo",
        "generate",
        "solve",
        "verify",
        "replan",
        "compare",
    ):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=name != "verify")
        command.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            command.add_argument("--profile", choices=("ci", "standard"), default="ci")
        if name == "generate":
            command.add_argument("--customers", type=int, default=25)
            command.add_argument("--tight", action="store_true")
        if name in ("solve", "verify", "replan"):
            command.add_argument("--instance", type=Path, required=True)
        if name == "verify":
            command.add_argument("--plan", type=Path, required=True)
        if name in ("solve", "replan"):
            command.add_argument("--iterations", type=int, default=100)
            command.add_argument("--seconds", type=float)
        if name == "solve":
            command.add_argument("--exact", action="store_true")
        if name == "replan":
            command.add_argument("--previous-instance", type=Path, required=True)
            command.add_argument("--previous-plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            report = verify(read_instance(args.instance), read_plan(args.plan))
            print(json.dumps(asdict(report)))
            if not report.valid:
                raise SystemExit(1)
            return
        if args.command == "clean-demo":
            clean_output(args.output)
            return
        output = output_directory(args.output)
        if args.command == "demo":
            demo(output, args.seed)
        elif args.command == "benchmark":
            report_json = run_benchmark(
                args.profile, output, args.seed, Path(__file__).resolve().parents[2]
            )
            print(
                json.dumps(
                    {"status": report_json["status"], "output": str(output / "benchmark.json")}
                )
            )
            if report_json["status"] != "passed":
                raise SystemExit(1)
        elif args.command == "generate":
            write_json(
                output / "instance.json",
                instance_dict(island(args.customers, args.seed, tight=args.tight)),
            )
        elif args.command == "solve":
            instance = read_instance(args.instance)
            result = (
                exhaustive(instance)
                if args.exact
                else solve(instance, SearchBudget(args.iterations, args.seconds), seed=args.seed)
            )
            save_result(instance, result, output)
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "objective": result.plan.objective if result.plan else None,
                        "iterations": result.iterations,
                        "stopping_reason": result.stopping_reason,
                    }
                )
            )
        elif args.command == "compare":
            instance = tiny()
            reference = exhaustive(instance)
            heuristic = solve(instance, SearchBudget(250), seed=args.seed)
            write_json(
                output / "result.json",
                {"reference": asdict(reference), "heuristic": asdict(heuristic)},
            )
        elif args.command == "replan":
            expanded = read_instance(args.instance)
            instance = prepare_replan(
                read_instance(args.previous_instance),
                read_plan(args.previous_plan),
                expanded,
                expanded.states,
            )
            result = solve(instance, SearchBudget(args.iterations, args.seconds), seed=args.seed)
            save_result(instance, result, output)
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "objective": result.plan.objective if result.plan else None,
                    }
                )
            )
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"routecraft: {error}\n")


if __name__ == "__main__":
    main()
