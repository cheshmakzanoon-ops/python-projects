# Run and diagnose

Install with `uv sync --locked --python 3.13.16` or the tested 3.14.8 default.
Use `UV_CACHE_DIR=/workspace/.cache/uv UV_PYTHON_INSTALL_DIR=/workspace/.python`
on the shared cloud machine. No service, credential, network API or paid dataset
is required after dependency installation. For scientific measurements set
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`; reserve a serial
benchmark lease. Set `MPLCONFIGDIR`/`XDG_CACHE_HOME` to an owned writable directory
in a restricted environment. No server or background workers are left running.

SDK and JSON instances must list customer records in ascending matrix-node ID
order (1..n). Public `construct` raises `ValueError` for invalid input; `solve`
and the reference solver return `INVALID_INPUT`. Reorder records before calling
these interfaces rather than interpreting this validation error as infeasibility.

Generate an input, solve it, then verify independently:

```bash
uv run --locked python -m pp_routecraft.cli generate --customers 25 --output /tmp/rc-input
uv run --locked python -m pp_routecraft.cli solve --instance /tmp/rc-input/instance.json \
  --iterations 100 --output /tmp/rc-solved --seed 1729
uv run --locked python -m pp_routecraft.cli verify --instance /tmp/rc-input/instance.json \
  --plan /tmp/rc-solved/plan.json
```

`--seconds` adds a cooperative wall limit. Zero seconds without an existing
incumbent returns `NO_FEASIBLE_PLAN_FOUND`, never proven infeasibility. In Python,
pass `initial=verified_plan` and `cancelled=callback` to retain an incumbent through
cancellation. Stop conditions are checked before construction, before a fallback constructor, and before each search operation; an observed cancellation cannot be undone by a later callback result. Only tiny `solve --exact` can prove infeasibility. Invalid API input
returns `INVALID_INPUT`; CLI invalid input/budgets, malformed JSON and file errors exit 2, preserving any solver diagnostics in `result.json`; verifier rejection
exits 1. A heuristic unknown result is represented in its JSON result, not hidden.

For a rolling update, supply an expanded instance with one state per vehicle and
run `replan --previous-instance OLD --previous-plan PLAN --instance EXPANDED
--output /tmp/rc-replanned`. Existing matrix entries must match byte-equivalent
integer costs. Each started vehicle's `loaded` entries must be exactly its old
uncompleted route jobs. `onboard` equals their quantity sum. `node` is the last
executed customer or depot, `time` is the actual departure boundary, and `boundary`
is `departure` or `service_complete`. The demo emits a valid example.

Back up input, previous plan and states together; they are the reproducible state.
No database or recovery daemon is involved. Restore by verifying the plan against
its input before replanning. A JSON objective can be inspected but is not trusted.
Change a route's objective or duplicate a customer to trigger verifier diagnostics.

Outputs require an absolute, empty or explicitly owned directory. Symlinks in the output path, any ancestor, ownership marker, or fixed output filename are rejected before writing or cleanup.
`clean-demo --output /tmp/routecraft-demo` deletes only fixed Routecraft-owned
filenames and its exact ownership marker; unrelated files survive. It refuses
unowned directories and symlink targets. Never use a generic recursive removal
command to reset arbitrary user data.

The [JSON contract](FORMAT.md) lists accepted fields and defaults. Unknown fields, duplicate object keys and unsupported schema versions fail explicitly. A matrix version must be a nonempty string.

Checks: `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, `uv run --locked mypy src`, `uv run --locked pytest`, `uv build`.
Run the wheel-installed demo from outside the source tree as a packaging check.

The timeline uses verified durations. Delays between an executed prefix and the actual departure boundary appear separately from travel; zero-duration service appears as a tick. For earlier executed visits, the report replays the model's earliest feasible history, not a full timestamped execution log. Keep the original instance and state sequence if actual historical timestamps are required.
