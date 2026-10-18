#!/usr/bin/env bash
# Reproduce the dependency layer; services restart separately at task startup.
set -eu
cd /workspace/python-projects
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PYTHON_INSTALL_DIR=/workspace/.python
export UV_LINK_MODE=copy
export PORTFOLIO_PYTHON=3.14.8
uv --version
uv python install --no-bin 3.13.16 3.14.8
uv sync --locked --project tooling/quality --python 3.13.16
for project in anchor strata current meridian quarry pytrace atlas proving-ground routecraft resonance; do
  python scripts/portfolio.py setup "$project"
done
docker pull postgres:17@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3
python scripts/portfolio.py doctor
