# Reusable cloud environment

This checkout is `/workspace/python-projects`. uv 0.12.23 manages independent locks and environments; CPython 3.14.8 is every product's default and 3.13.16 remains required. The dispatcher itself uses the image's Python 3.12 standard library. No root uv workspace combines product dependencies.

The tested dependency installation script is [cloud_install.sh](../scripts/cloud_install.sh):

```sh
bash scripts/cloud_install.sh
```

It checks both interpreter installations, syncs eleven locked environments (ten products plus quality tooling), pulls the pinned PostgreSQL image and checks the bootstrap. It changes generated environments/caches, not source or lockfiles. Repeated execution is supported. `/workspace/.cache/uv` and `/workspace/.python` are writable; the image's home directory is read-only.

Processes and connections do not survive an environment snapshot. Start the two separate loopback-only synthetic development databases:

```sh
python scripts/services.py up anchor
python scripts/services.py up meridian
python scripts/services.py status anchor
python scripts/services.py status meridian
export ANCHOR_DATABASE_URL="$(python -c 'import json; print(json.load(open(".local/services/anchor.json"))["url"])')"
export MERIDIAN_DATABASE_URL="$(python -c 'import json; print(json.load(open(".local/services/meridian.json"))["url"])')"
export MERIDIAN_PG_CONTAINER=pp-meridian-dev
```

The helper checks `pg_isready`, allocates distinct ephemeral host ports and records only local synthetic connection metadata under ignored `.local/services`. Local trust authentication is limited to these loopback demo containers; this is not a shared deployment configuration. Actual tests and demos exercise transactions and backup/restore; readiness alone is not functional verification. To remove only one owned container, use `python scripts/services.py down anchor` or `down meridian`. Never prune unrelated containers.

Use the existing checkout directly; do not create worktrees. Read `AGENTS.md` and project runbooks before development. Numerical threads are capped by the dispatcher. Heavy standard benchmarks run serially, using a scratch filesystem with enough space. Final verification uses disposable local Git clones, preserving exact provenance while isolating interpreter environments:

```sh
python scripts/verify_snapshot.py --python 3.14.8 --temp-root /workspace --output /workspace/python-projects/.local/new-verification
```

Outputs must be fresh. Explicit `--project` filters are available. Required services are inherited from exported URLs or the helper metadata. Clean clones install locked dependencies independently, build wheels, run full installed-wheel demos outside source and retain command exit statuses and hashes.

The tested install script and service startup instructions are also saved as a cloud configuration draft. Saving is separate from applying settings or publishing a snapshot. Fresh-task restoration and other operating systems are not claimed without separate evidence. Core workflows need no paid API, GPU or external dataset.
