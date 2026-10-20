"""Install a built wheel outside the source tree and import its public package."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    project = Path(sys.argv[1]).resolve()
    wheel_directory = Path(sys.argv[4]) if len(sys.argv) > 4 else project / "dist"
    wheels = list(wheel_directory.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel; use a fresh build directory")
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
                (sys.argv[3] if len(sys.argv) > 3 else None)
                or os.environ.get("PORTFOLIO_PYTHON")
                or (project / ".python-version").read_text().strip(),
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
        output = Path(folder) / "owned-demo"
        try:
            subprocess.run(
                [
                    str(python),
                    "-I",
                    "-m",
                    f"{sys.argv[2]}.cli",
                    "demo",
                    "--output",
                    str(output),
                    "--seed",
                    "1729",
                ],
                cwd=folder,
                env=environment,
                check=True,
                timeout=300,
            )
        finally:
            if output.exists():
                cleanup = subprocess.run(
                    [
                        str(python),
                        "-I",
                        "-m",
                        f"{sys.argv[2]}.cli",
                        "clean-demo",
                        "--output",
                        str(output),
                    ],
                    cwd=folder,
                    env=environment,
                    check=False,
                    timeout=60,
                )
                if cleanup.returncode:
                    raise RuntimeError(
                        "installed demo cleanup failed; see owned output diagnostics"
                    )


if __name__ == "__main__":
    main()
