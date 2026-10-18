"""Install a built wheel outside the source tree and import its public package."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    project = Path(sys.argv[1]).resolve()
    wheels = sorted((project / "dist").glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit("No built wheel")
    with tempfile.TemporaryDirectory(prefix="portfolio-wheel-") as folder:
        environment = os.environ.copy()
        python = Path(folder) / (
            "venv/Scripts/python.exe" if os.name == "nt" else "venv/bin/python"
        )
        subprocess.run(
            [
                "uv",
                "venv",
                "--python",
                os.environ.get("PORTFOLIO_PYTHON", "3.13"),
                str(Path(folder) / "venv"),
            ],
            env=environment,
            check=True,
        )
        constraints = Path(folder) / "constraints.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements-txt",
                "--output-file",
                str(constraints),
            ],
            cwd=project,
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--constraint",
                str(constraints),
                str(wheels[-1]),
            ],
            env=environment,
            check=True,
        )
        subprocess.run(
            [str(python), "-I", "-c", f"import {sys.argv[2]}; print({sys.argv[2]}.__file__)"],
            cwd=folder,
            check=True,
        )
        subprocess.run(
            [str(python), "-I", "-m", f"{sys.argv[2]}.cli", "--help"],
            cwd=folder,
            check=True,
            stdout=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
