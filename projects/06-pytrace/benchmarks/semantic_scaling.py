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
import time
from pathlib import Path

import pp_pytrace
from pp_pytrace.analysis.engine import Analyzer
from pp_pytrace.frontend.discovery import parse


def source_for(functions: int) -> str:
    return "import os\n" + "".join(
        f'def case_{index}(flag):\n command="safe"\n try:\n  if flag:\n   command=input()\n finally:\n  os.system(command)\n'
        for index in range(functions)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    package = Path(pp_pytrace.__file__).parent
    files = sorted(package.rglob("*.py"))
    package_hash = hashlib.sha256(
        b"".join(
            path.relative_to(package).as_posix().encode() + b"\0" + path.read_bytes()
            for path in files
        )
    ).hexdigest()
    measurements = []
    for functions in (100, 300, 900):
        source = source_for(functions)
        tree = parse(source)  # Parsing/startup excluded deliberately.
        timings = []
        for _ in range(3):
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
                "median_seconds": statistics.median(timings),
                "blocks": result.blocks,
                "transfer_steps": result.iterations,
                "diagnostics": len(result.diagnostics),
                "shell_findings": functions,
            }
        )
    report = {
        "schema_version": 1,
        "label": args.label,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_path": str(package),
        "package_content_sha256": package_hash,
        "scope": "Three analysis-only repeats on pre-parsed identical ASTs; includes analyzer construction, CFG, fixed point, lexical scopes and diagnostics; excludes parsing/cache/I/O",
        "limitation": "Synthetic functions, one shared host; describes this mechanism, not production throughput or broad analyzer accuracy",
        "measurements": measurements,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
