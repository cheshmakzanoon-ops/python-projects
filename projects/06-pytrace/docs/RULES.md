# Rule semantics and interpretation

PyTrace is an intraprocedural may-analysis. A finding identifies a modeled path
or an uncertain flow worth inspecting; it is not proof that every execution is
vulnerable. Conversely, no finding is not evidence of safety across an unsupported
construct. PT900 warns about modeled coverage boundaries and participates in
`--fail-on-findings`.

## PT001: shell-enabled process calls

A configured source, such as `input()` or `os.getenv()`, introduces independent
shell and SQL taint. Imports and assignments retain canonical call targets.
`subprocess.run`, `call`, `Popen`, `check_call` and `check_output` are shell sinks
when `shell` is truthy or its value cannot be determined. Unresolved `**options`
can enable a shell. `os.system` is a direct shell sink.

```python
import subprocess as process

command = input()
process.run(command, shell=True)  # PT001: configured source reaches shell.
process.run(["printf", "%s", command], shell=False)  # No modeled shell flow.
```

`shlex.quote` removes shell taint only when its binding is unambiguous. It does
not establish correctness for an arbitrary shell language or argument context,
and does not remove SQL taint. Unknown calls preserve argument/receiver taint
and unknown status. A possible sink mixed with another target is uncertain;
confidence is computed after the complete control-flow join.

## PT002: constructed or untrusted SQL

The default `execute`/`executemany` method protocol is structural. PyTrace does
not prove that the receiver is a database cursor, so non-database methods with
those names can produce false positives. Configure the protocol for the codebase.

```python
query = "SELECT * FROM users WHERE name = " + input()
cursor.execute(query)  # PT002.
cursor.execute("SELECT * FROM users WHERE name = ?", (input(),))
```

The second call keeps query text fixed and data separate. Supplying parameters
does not sanitize an already interpolated query. Driver placeholder conventions,
identifier quoting and query semantics are not inferred. A shell sanitizer
cannot establish SQL safety. Custom SQL sanitizers require their own trusted,
context-specific contract.

## PT003: synchronous blocking in async functions

Configured targets include `time.sleep`, common synchronous HTTP requests and
blocking process APIs. Import aliases are resolved and local shadowing is
respected. An asynchronous lexical function containing such a call is reported;
PyTrace does not measure duration or infer that an arbitrary wrapper offloads it.

```python
from time import sleep as delay


async def service():
    delay(1)  # PT003.
```

Class bodies and definition defaults/decorators execute where the definition is
encountered. Functions nested beneath them are analyzed separately. General
scheduler behavior and dynamically generated callables remain outside the model.

## Control-flow examples that change the result

Cleanup is executable code even when a function returns:

```python
import os


def service():
    try:
        return 0
    finally:
        os.system(input())  # PT001; return does not bypass finally.
```

An empty iterable does not overwrite its target:

```python
run = os.system
for run in []:
    pass
run(input())  # PT001; the original binding is still present.
```

Exception aliases and pattern captures are locals throughout a function. A use
before the binding cannot borrow an identically named module import. Handler
aliases are cleared after the handler. This prevents invented sink resolutions
on paths where CPython would raise an unbound-name error.

The analyzer is path-insensitive at joins and does not prove arbitrary predicates.
For example, two separate tests of the same flag are not correlated. A false
positive can therefore survive even when a human can show the source branch and
sink branch are mutually exclusive. Prefer reviewing the flow and narrowing
configuration over treating a high confidence label as a probability.

## Diagnostics and operational decisions

| Field/result | Meaning |
| --- | --- |
| `high` confidence | A configured flow within the modeled binding/value subset |
| `uncertain` confidence | Unknown data, alias, flag or receiver participates |
| `modeled` coverage | The diagnostic uses supported transfer semantics |
| `partial` coverage / PT900 | An explicit language or call-summary boundary applies |
| PT901 | Bounded parsing/compilation failed; the file was not analyzed |
| Resource-budget error | Analysis aborted; no complete result or cache is published |

Evidence lists up to eight source-line witnesses and the sink. It is not a full
execution trace or a proof covering all possible sources. Function call graphs,
general heap aliases, reflection, context-manager suppression, `except*`
subgroups and partially bound failed patterns require manual review. See
[operations](OPERATIONS.md) for configuration, failure handling and reproducible
checks.
