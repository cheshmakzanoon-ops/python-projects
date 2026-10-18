# Operations

Install the independently locked project with `uv sync --locked --python
3.14.8` (3.13.16 is also required and tested). No service is required. All low-level fault suites require Linux and
a local writable filesystem. Run processes with bounded timeouts. Database paths
are caller-selected directories; all database internals are owned by Strata.
Do not place unrelated files or symlinks inside them. Strata rejects internal
symlinks rather than following a WAL or manifest outside the selected directory.

```sh
uv run --locked python -m pp_strata.cli inspect /absolute/database
uv run --locked python -m pp_strata.cli verify /absolute/database
uv run --locked python -m pp_strata.cli compact /absolute/database
uv run --locked python -m pp_strata.cli backup /absolute/database /absolute/new-backup
uv run --locked python -m pp_strata.cli restore /absolute/new-backup /absolute/new-restored
```

Each command obtains the exclusive process-owner lock. Stop the application
owner before using operator commands. `inspect` reports current/checkpoint
sequences, active snapshots, files, cache counters, and size; `verify` checks all
live block checksums/order. These commands can perform normal open recovery,
including truncating an incomplete WAL tail and retiring orphan tables. They
are not forensic read-only file viewers. Preserve a filesystem copy first when
investigating corruption.

On `WriterFailed`, keep any required previously published reads, close all
handles, and reopen. Recovery may include a complete batch whose original caller
received an exception. Application-level operation IDs or idempotent writes are
needed when resolving this acknowledgement ambiguity. Do not retry indefinitely
inside a poisoned owner. Repairing a CRC mismatch by editing checksums is not
supported: preserve the files and restore a validated backup.

Backups refuse an existing destination and paths inside the source database.
The returned report identifies the source snapshot and content digest. Use
`db.backup(new_path, snapshot=old_snapshot)` to export a retained historical view.
`restore` validates a backup's entire live content digest, then writes a new
database; it never replaces an existing directory. A failed backup leaves its
partial new directory for inspection. A backup is not encrypted.

Demo outputs require an absolute directory and an exact Strata marker. A
nonempty unmarked directory is refused. `clean-demo --output /absolute/output`
removes only fixed directly owned paths and the marker; unrelated direct files
survive. It rejects symlink children. Keep generated runs outside tracked source.

```sh
uv run --locked pytest --cov --cov-report=term-missing
uv run --locked python benchmarks/extended_stateful.py --jobs 2 --output /tmp/strata-stateful.json
uv run --locked python -m pp_strata.cli benchmark --profile ci --output /tmp/strata-ci --seed 1729
uv run --locked python -m pp_strata.cli clean-demo --output /tmp/strata-ci
```

Run the standard profile alone with BLAS/OpenMP thread counts set to one
(Strata itself has no numerical kernels). The extended stateful runner requires
100 seeds × 5,000 operations by default and periodically closes/reopens each
database. Smaller flags are for diagnosis and do not close that required gate.
`--jobs 2` bounds independent owning processes to two; default is one. Results
are sorted by seed and checkpointed after each completed seed. Reuse an existing
output only with `--resume`; source digest, interpreter, seed count, and operation
count must match. A partial checkpoint has status `running`, never `passed`.
