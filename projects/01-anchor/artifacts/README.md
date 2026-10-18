# Authentic development evidence

These small captures come from actual local runs, with synthetic generated inputs:

- `development-baseline-ci.json`: first five-repetition ci baseline and 100k future timer
  probe. It records its exact dirty source digest, commit, lock, root contract and host.
  Queue indexes and stronger validation were added afterward; this is historical evidence,
  not final-source certification or a controlled performance comparison.
- `development-demo-history.json` / `development-demo-timeline.txt`: actual export, worker
  kill after effect, epoch-two recovery, one publication and replay verification. The
  schema/run identity is generated, not a required hardcoded fixture.

Final release verification must run against the coordinator's immutable committed source.
Generated large runtime state stays outside Git. No benchmark log contains a database URL.
