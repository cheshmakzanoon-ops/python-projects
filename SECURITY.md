# Security

These products are designed for local development and evaluation with synthetic, caller-selected data. They are not a shared hosting platform. Demonstration services bind to loopback, and development databases use trust authentication inside isolated containers. Do not expose those databases, demo identities, or tokens to another machine.

## Trust boundaries

| Surface | Implemented boundary | Operator responsibility |
| --- | --- | --- |
| HTTP services | Authentication where specified, tenant membership checks, bounded requests and validated inputs | Keep local services private; terminate TLS and apply deployment-specific access controls before shared use |
| Local databases | Transactional invariants, format checks, bounded public cursors | Use dedicated databases and identities; protect files and backups with operating-system permissions |
| Source analysis | Static parsing and bounded analysis; supported source edits require explicit commands | Review proposed edits; do not run analyzed programs as part of inspection |
| Model artifacts | Recorded provenance, allowlisted estimator loading, promotion checks | Treat artifacts as trusted executable material; hashes do not make hostile serialization safe |
| Snapshots and reports | Product-specific ownership, containment and integrity checks | Keep valuable data outside demo directories; do not allow an untrusted local user to replace files concurrently |
| Development containers | Pinned image digest, ownership label, loopback port validation | Use a local daemon; never run the helper against a shared production Docker context |

Individual runbooks document narrower guarantees. Database durability depends on the filesystem and storage stack. Crash tests exercise process termination and selected I/O failures, not every hardware failure. Request limits reduce individual request cost; they do not provide traffic-level rate limiting or a complete denial-of-service defense.

## Reporting a vulnerability

Use GitHub private vulnerability reporting if it is available for this repository, or a private contact published by the owner. No dedicated security mailbox or response-time commitment is currently published. If no private route is available, open an issue asking for a contact without including exploit details or sensitive data.

Include the affected commit and package, supported Python version, a minimal reproduction using synthetic data, expected and observed behavior, and the security impact. Redact credentials, connection strings to private systems, personal records, and private documents. Do not publish a working exploit before coordinating disclosure.

## Maintenance and deployment

Security fixes target the current main branch; no historical release maintenance policy is offered. Dependencies are pinned in each `uv.lock`, Actions use immutable commit references, and CI has read-only repository permissions. Update locks deliberately, run the supported interpreter matrix, and review advisories for both direct and transitive dependencies.

Run `python scripts/audit_dependencies.py --output .local/advisories-new` with a fresh output path to audit all ten runtime locks using pinned pip-audit and PyPI's advisory data. This exports exact hashes without installing product packages. Service failures, incomplete reports, skipped packages, and known vulnerabilities fail the command. The scheduled dependency workflow retains these reports as artifacts. Results cover the packages applicable to the audit interpreter (CPython 3.14.8); development tools and other platform combinations need separate review. An advisory scan does not inspect application authorization or prove that dependencies are free of unknown vulnerabilities.

A shared deployment additionally needs its own authentication lifecycle, authorization review, TLS, network restrictions, secret storage, traffic limits, backup/restore policy, monitoring, and dependency update process. No security certification or production operation is claimed for these portfolio demonstrations.
