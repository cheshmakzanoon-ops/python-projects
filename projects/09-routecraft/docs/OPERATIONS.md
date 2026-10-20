# Run and diagnose

Install the default with `uv sync --locked --python 3.14.8`. Use
`UV_PROJECT_ENVIRONMENT="$PWD/../../.local/venvs/routecraft-3.13.16" uv sync --locked --python 3.13.16`
for the separate compatibility environment; do not replace the editor's default
environment while another check is running.
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
cancellation. Stop conditions are checked before construction, before a fallback
constructor, before each search operation and at the final completed-operation
boundary. A zero-iteration budget permits initial construction unless another
stop is already observed; it does not suppress the final deadline/cancellation
check. An observed cancellation cannot be undone by a later callback result.
Only tiny `solve --exact` can prove infeasibility. Invalid API input
returns `INVALID_INPUT`; CLI invalid input/budgets, malformed JSON and file errors exit 2, preserving any solver diagnostics in `result.json`; verifier rejection
exits 1. A heuristic unknown result is represented in its JSON result, not hidden.

For a rolling update, supply an expanded instance with one state per vehicle and
run `replan --previous-instance OLD --previous-plan PLAN --instance EXPANDED
--output /tmp/rc-replanned`. Existing matrix entries must match byte-equivalent
integer costs. Each started vehicle's `loaded` entries must be exactly its old
uncompleted route jobs. `onboard` equals their quantity sum. `node` is the last
executed customer or depot, `time` is the actual departure boundary, and `boundary`
is `departure` or `service_complete`. The demo emits a valid example.

Use the history-validation boundary in Python too:

```python
from pp_routecraft import SearchBudget, prepare_replan, solve, verify

rolling = prepare_replan(previous_instance, previous_plan, expanded_instance, actual_states)
result = solve(rolling, SearchBudget(iterations=100), seed=1729)
if result.plan is not None:
    assert verify(rolling, result.plan).valid
```

`actual_states` must describe every vehicle, including idle ones. A started truck
keeps exactly its previous uncompleted deliveries; quantity and customer identity
are both checked. An unstarted truck can load added work. Preserve the previous
instance, plan and each state sequence before requesting the next update. Repeating
an update must not reset `started`, shorten/reorder the completed prefix or move
actual time backward. Delays may make the remaining problem infeasible; increasing
an iteration budget does not authorize shifting historical boundaries or moving
cargo to another truck.

Directed travel need not satisfy the triangle inequality. For example, a completed
prefix at node 1 can have `travel[1][0]=100` while the remaining onboard delivery
allows `1→2→0` in two units. A shift of ten units forbids direct return but permits
the continuation. Construction now tries that insertion rather than discarding the
partial route. It uses full candidate scheduling when the partial route has no
feasible timing profile. Several deliveries may still need joint insertion to
produce any feasible intermediate route; the heuristic has no completeness proof.

If a rolling search reports `NO_FEASIBLE_PLAN_FOUND`, first verify the previous
plan against the new state-bearing instance. If it remains valid and covers all
current customers, it can be passed as `initial=previous_plan` to retain that known
continuation. When new customers have been added it is incomplete and must not be
used as an initial incumbent. Preserve the failed result and inspect exact cargo,
windows, actual departure, return shift and immutable matrix entries. For supported
static tiny instances, exhaustive search distinguishes infeasibility from heuristic
failure; snapshots themselves are outside the exact reference's domain.

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

Insertion certificates are transaction-free, repair-local caches. They are derived
from the supplied instance and feasible partial route and are never serialized as
authoritative state. There is no cache file to repair or invalidate after a crash.
Rerun from the saved inputs/state and verify the returned complete plan. The exact
reference and verifier use separate timing implementations; an internal disagreement
raises an error and must be investigated rather than bypassed by editing cached
schedules or objective values.

The timeline uses verified durations. Delays between an executed prefix and the actual departure boundary appear separately from travel; zero-duration service appears as a tick. For earlier executed visits, the report replays the model's earliest feasible history, not a full timestamped execution log. Keep the original instance and state sequence if actual historical timestamps are required.
