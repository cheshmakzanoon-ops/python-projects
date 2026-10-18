# Shared requests

Coordinator: after both interpreter checks, set Routecraft default Python to
3.14.8, required versions 3.13.16 and 3.14.8, no required services. Pure solver/CLI
supports CPython on Linux/macOS/Windows; benchmark RSS is null on platforms
without POSIX `resource`, byte-scaled on macOS and KiB-scaled on Linux. Measurements
are Linux-only in this handoff.
Run standard 25/100/500 multi-seed benchmark serially after source commit; worker
has not started a standard benchmark. No integration depends on this package.
