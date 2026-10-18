"""Validate local Markdown links and build the root documentation offline."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    ".local",
    "dist",
    "site",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def main() -> int:
    failures: list[str] = []
    checked = 0
    for path in ROOT.rglob("*.md"):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        text = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1\s*$", "", path.read_text(encoding="utf-8"))
        for match in re.finditer(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
            target = match.group(1).strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = (path.parent / unquote(parsed.path)).resolve()
            if not destination.is_relative_to(ROOT):
                failures.append(f"{path.relative_to(ROOT)}: path escapes repository: {target}")
            elif not destination.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing target: {target}")
            checked += 1
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"Checked {checked} local documentation links; {len(failures)} failures.")
    if failures:
        return 1
    command = [
        "uv",
        "run",
        "--locked",
        "--project",
        "tooling/quality",
        "mkdocs",
        "build",
        "--strict",
        "--site-dir",
        str(ROOT / ".local/docs-site"),
    ]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
