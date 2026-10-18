# Small Python pipeline

The README's six-line record submission uses only the installed public package. A caller preparing NDJSON can serialize `Record.wire()` plus a newline and use `current replay --input events.ndjson --output /tmp/fresh-current-replay`. Register every input before execution; always journal explicit control records in the intended order. The default demo generator is in `pp_current.diagnostics.workload.generate` and is deterministic under the recorded seed.
