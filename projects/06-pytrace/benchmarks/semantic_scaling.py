"""Focused analysis-only scaling; generated source is parsed, never executed.

Run from the project directory. PYTHONPATH can select an independently exported
historical package for a baseline; the report records the imported package hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import pp_pytrace
from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.frontend.discovery import parse


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("repetitions must be a positive integer")
    return number


def digest_code(package: Path) -> str:
    return hashlib.sha256(
        b"".join(
            path.relative_to(package).as_posix().encode() + b"\0" + path.read_bytes()
            for path in sorted(package.rglob("*.py"))
        )
    ).hexdigest()


def imported_modules(package: Path) -> dict[str, str]:
    paths = {
        name: str(Path(module.__file__).resolve())
        for name, module in sorted(sys.modules.items())
        if (name == "pp_pytrace" or name.startswith("pp_pytrace."))
        and getattr(module, "__file__", None) is not None
    }
    if any(not Path(path).is_relative_to(package) for path in paths.values()):
        raise RuntimeError("Imported PyTrace modules must come from one package snapshot")
    return paths


def source_for(functions: int) -> str:
    return "import os\n" + "".join(
        f'def case_{index}(flag):\n command="safe"\n try:\n  if flag:\n   command=input()\n finally:\n  os.system(command)\n'
        for index in range(functions)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--repetitions", type=positive_int, default=5)
    args = parser.parse_args()
    package = Path(pp_pytrace.__file__).resolve().parent
    package_hash = digest_code(package)
    workload_path = Path(__file__).resolve()
    workload_hash = hashlib.sha256(workload_path.read_bytes()).hexdigest()
    measurements = []
    for functions in (100, 300, 900):
        source = source_for(functions)
        tree = parse(source)  # Parsing/startup excluded deliberately.
        timings = []
        for _ in range(args.repetitions):
            start = time.perf_counter()
            result = Analyzer(source, "scale.py").run(tree)
            timings.append(time.perf_counter() - start)
            assert sum(item.rule_id == "PT001" for item in result.diagnostics) == functions
        measurements.append(
            {
                "functions": functions,
                "bytes": len(source.encode()),
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "seconds": timings,
                "measurement_runs": len(timings),
                "median_seconds": statistics.median(timings),
                "blocks": result.blocks,
                "transfer_steps": result.iterations,
                "diagnostics": len(result.diagnostics),
                "shell_findings": functions,
            }
        )
    if (
        digest_code(package) != package_hash
        or hashlib.sha256(workload_path.read_bytes()).hexdigest() != workload_hash
    ):
        raise RuntimeError("Package or workload source changed during measurement")
    report = {
        "schema_version": 2,
        "workload": "pytrace-semantic-scaling-v2",
        "label": args.label,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_path": str(package),
        "package_content_sha256": package_hash,
        "package_inputs": [
            path.relative_to(package).as_posix() for path in sorted(package.rglob("*.py"))
        ],
        "imported_modules": imported_modules(package),
        "workload_path": str(workload_path),
        "workload_sha256": workload_hash,
        "repetitions": args.repetitions,
        "inputs_unchanged": True,
        "scope": "Analysis-only repeats on pre-parsed identical ASTs; includes analyzer construction, CFG, fixed point, lexical scopes and diagnostics; excludes parsing/cache/I/O",
        "limitation": "Synthetic functions, one shared host; describes this mechanism, not production throughput or broad analyzer accuracy",
        "measurements": measurements,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
