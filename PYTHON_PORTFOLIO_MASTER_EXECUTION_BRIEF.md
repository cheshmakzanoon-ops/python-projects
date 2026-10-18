# Python Portfolio — Master Execution Brief

**Target repository:** https://github.com/cheshmakzanoon-ops/python-projects.git  
**Deliverable:** ten substantial, independently runnable Python projects in one professional GitHub repository  
**Execution model:** one coordinating agent and ten specialist implementation agents working concurrently when the runtime permits  
**Working branch:** main; one coordinator owns all Git mutations  
**Prepared:** October 17, 2026, America/Halifax; repository inspection occurred October 18, 2026 UTC  
**Document status:** implementation instructions, not a claim that any of the projects has already been built or benchmarked

---

## 0. Instructions to the executing agent

You are the lead Python engineer responsible for delivering this repository. Read this brief completely, inspect the actual repository, and implement the specified portfolio. You are responsible for architecture, integration, verification, and the final repository experience. Delegate the ten project implementations to ten specialist agents.

Produce working software. A plan, a directory tree, disconnected examples, generated API stubs, or ten attractive READMEs do not satisfy this assignment. Each project needs an original engineering core, a usable interface, difficult correctness tests, a reproducible demonstration, and an honest account of its limitations.

The desired standard is the engineering judgment associated with an experienced senior Python developer: explicit contracts, appropriate abstractions, reliable behavior under failure, profiling, maintainable code, useful operational tooling, and evidence that another developer can reproduce. Ten projects cannot manufacture ten years of professional experience. Do not describe this portfolio as employment, client work, or production usage that did not happen.

Continue through implementation, integration, defect correction, and verification. Finish all required acceptance scenarios. If an external constraint genuinely prevents a step, record the exact blocked gate and continue everything independent of it. Do not silently downgrade scope, invent a successful run, or declare the whole portfolio complete while a required project is missing.

### How to read this document

**Quick navigation:** [Projects and ownership](#2-the-ten-projects-and-their-engineering-purpose) · [Agent protocol](#4-ten-agent-execution-protocol) · [Acceptance and CI](#6-common-commands-ci-and-global-delivery-gates) · [Integration demos](#17-coordinator-owned-integration-demonstrations) · [Launch prompt](#21-copy-paste-launch-prompt)

1. Sections 1–6 define the repository, team, shared standards, and completion protocol.
2. Sections 7–16 are the ten implementation contracts, one per project agent.
3. Sections 17–21 define integration, the portfolio presentation, execution phases, final acceptance, and launch instructions.
4. Section 22 records technical references and what they support.

Every requirement marked **required**, every project acceptance ID, and every global gate must be implemented and verified. Features explicitly labeled **optional extension** are outside the completion gate. Do not spend time on optional extensions while required work remains.

---

## 1. Verified repository starting point and scope

At inspection, the public repository existed, its default branch was main, and its root contained only a 17-byte README.md containing the heading “python-projects.” The inspected main commit was:

~~~text
4adce84a900eeb903f427b73a7be279e3cb43632
~~~

Source: [the inspected commit](https://github.com/cheshmakzanoon-ops/python-projects/commit/4adce84a900eeb903f427b73a7be279e3cb43632) and [its README](https://github.com/cheshmakzanoon-ops/python-projects/blob/4adce84a900eeb903f427b73a7be279e3cb43632/README.md).

This observation is a starting snapshot. Reinspect before editing. Preserve any work added since that commit. Do not reset the repository to the inspected version.

### Scope boundaries

- Build ten independent products with a common development experience.
- The repository is a portfolio monorepo, not one giant application requiring ten services to run.
- Each project must be installable and demonstrable without importing another portfolio project's implementation.
- Cross-project demonstrations use files or documented HTTP contracts and are integration examples, not runtime dependencies.
- Core product behavior must work locally after dependency installation. No paid APIs, proprietary datasets, GPU, cloud account, or external credentials are mandatory.
- Local PostgreSQL and Docker Compose are allowed where database concurrency is part of the engineering problem.
- Heavy workloads run individually. Ten coding agents do not imply ten load tests or ten database stacks should run simultaneously.
- The complete required scope is substantial work. Do not promise completion in one sitting or claim background activity after the runtime stops.

### Licensing and provenance

Preserve existing license choices and notices. Track the source, license, modification status, and redistribution permissions of every external dataset, audio sample, model, icon, and code excerpt. Use generated fixtures or clearly permitted small assets for default demos. Do not copy another project's implementation and present it as original work.

If the repository has no chosen code license, record that fact and an explicit recommendation for the owner; do not invent an existing license. Building and testing can continue. Public registry publishing, paid deployment, outbound messages, and account changes are not part of this brief.

Package metadata and badges must also reflect the actual license status rather than inventing a license identifier.

---

## 2. The ten projects and their engineering purpose

| Agent | Project | Owned directory | Python import package | Primary engineering evidence |
| --- | --- | --- | --- | --- |
| A01 | **Anchor** — durable workflow engine | projects/01-anchor/ | pp_anchor | Async orchestration, durable state machines, replay, leases, retries, compensation |
| A02 | **Strata** — transactional embedded storage engine | projects/02-strata/ | pp_strata | WAL, SSTables, MVCC, snapshot isolation, compaction, crash recovery |
| A03 | **Current** — event-time stream processor | projects/03-current/ | pp_current | Watermarks, late events, stateful windows, backpressure, replay, checkpoints |
| A04 | **Meridian** — multi-tenant ledger and reconciliation backend | projects/04-meridian/ | pp_meridian | Django, PostgreSQL, transactional invariants, idempotency, authorization, accounting data |
| A05 | **Quarry** — incremental lakehouse and data-quality engine | projects/05-quarry/ | pp_quarry | Columnar data, incremental DAGs, lineage, schema evolution, snapshot publication |
| A06 | **PyTrace** — Python static analysis and safe refactoring toolkit | projects/06-pytrace/ | pp_pytrace | Parsing, control-flow graphs, dataflow analysis, source mapping, incremental analysis |
| A07 | **Atlas** — permission-aware document search engine | projects/07-atlas/ | pp_atlas | Inverted indexing, BM25, query planning, relevance evaluation, authorization |
| A08 | **Proving Ground** — reproducible ML experiment and promotion platform | projects/08-proving-ground/ | pp_proving_ground | Dataset lineage, leakage prevention, evaluation, artifact provenance, deployment state |
| A09 | **Routecraft** — routing and scheduling optimization engine | projects/09-routecraft/ | pp_routecraft | Constraint modeling, original heuristics, independent feasibility checks, simulation |
| A10 | **Resonance** — guitar audio analysis and transcription workbench | projects/10-resonance/ | pp_resonance | DSP, numerical computing, temporal decoding, evaluation, audio/MIDI tooling |

Project names are local portfolio brands, not claims of unique trademarks or available registry names. Distribution names should use the prefix pp-, such as pp-anchor and pp-proving-ground. Console entry points may use the readable project names inside their own environments.

### Avoid overlap

Anchor owns durable business coordination; Current owns event-time processing. Strata owns a storage implementation; Quarry uses established columnar engines and owns dataset transformation and publication semantics. PyTrace analyzes Python source; Atlas retrieves documents. Proving Ground governs repeatable ML experiments; Resonance solves an audio problem. Routecraft solves constrained optimization; Meridian enforces financial-record invariants.

Do not implement the same generic CRUD application ten times under different names.

### Original core versus dependencies

Use mature libraries for HTTP, database drivers, parsing support, numerical kernels, and cryptography. Implement the project-specific algorithm or domain logic yourself. The following substitutions do not satisfy the assignment:

- Anchor as a thin wrapper around Temporal, Celery, or Prefect.
- Strata as a wrapper around SQLite, Redis, RocksDB, or LMDB.
- Current as a Kafka consumer that forwards messages without implementing time/state semantics.
- Meridian as generated account CRUD with balance fields.
- Quarry as a notebook invoking DuckDB once.
- PyTrace as a subprocess wrapper around Ruff, mypy, or Semgrep.
- Atlas as a hosted search or LLM API client.
- Proving Ground as an MLflow installation with a different title.
- Routecraft as one OR-Tools call surrounded by endpoints.
- Resonance as a pretrained transcription service with an upload form.

---

## 3. Repository structure and ownership

### 3.1 Root layout

Use the following path contract. Create only files that have real content and a purpose.

| Path | Required contents | Owner |
| --- | --- | --- |
| README.md | Concise entry point, ten-project index, quick start, evidence and navigation | Coordinator |
| AGENTS.md | Ownership, commands, shared-file protocol, validation requirements, Git policy | Coordinator |
| CONTRIBUTING.md | Environment setup, project development, tests, commit conventions | Coordinator |
| SECURITY.md | Local demo assumptions, supported reporting route, known boundaries | Coordinator |
| THIRD_PARTY_NOTICES.md | Root index of project asset/dependency notices | Coordinator |
| portfolio.toml | Machine-readable project paths, package/CLI names, ports, test capabilities | Coordinator |
| ruff.toml | Shared lint/format defaults | Coordinator |
| .gitignore | Caches, virtual environments, local databases, private config, generated bulk outputs | Coordinator |
| .github/workflows/ci.yml | Changed-project checks and aggregate status | Coordinator |
| .github/workflows/extended.yml | Full matrix, longer failure suites, benchmark smoke on manual invocation | Coordinator |
| .github/ISSUE_TEMPLATE/ | Minimal bug and feature templates if useful | Coordinator |
| scripts/portfolio.py | Cross-platform task dispatcher using standard-library Python | Coordinator |
| tooling/quality/ | Independent tooling pyproject.toml, uv.lock, documentation dependencies | Coordinator |
| docs/PORTFOLIO_GUIDE.md | Recruiter and technical reviewer navigation | Coordinator |
| docs/STATUS.md | Verified state of every project and global gate | Coordinator |
| docs/architecture/ | Shared decisions, repository dependency and ownership map | Coordinator |
| docs/evidence/ | Small, reproducible repository-level verification records | Coordinator |
| docs/handoffs/ | Coordinator summaries of agent handoffs and unresolved integration issues | Coordinator |
| integrations/ | Small cross-project demonstrations and contract tests | Coordinator |
| projects/01-anchor/ through projects/10-resonance/ | Complete, separately packaged projects | Assigned agent |

Do not add Kubernetes, Terraform, a frontend monorepo, ten distinct dashboards, or a shared framework merely to make the root look large. Introduce new infrastructure only for a requirement in this brief or a measured operational need.

### 3.2 Each project must contain

| Path within its project | Purpose |
| --- | --- |
| pyproject.toml | Package metadata, runtime dependencies, development groups, typing/test config |
| uv.lock | Independently resolved, committed dependency lock |
| .python-version | Tested default interpreter for this project |
| src/pp_project/ | Installable implementation with explicit public exports |
| src/pp_project/py.typed | Typed-package marker when shipping an annotated library |
| tests/unit/ | Domain and algorithm tests with independent expected behavior |
| tests/property/ | Property/state-machine tests where applicable |
| tests/integration/ | Real persistence, processes, API, and component interaction |
| tests/acceptance/ | Named user stories corresponding to this brief |
| benchmarks/ | Seeded workload generators, runner, result schema |
| examples/ | Small runnable inputs and explanations |
| docs/ARCHITECTURE.md | Components, data flow, ownership, failure boundaries |
| docs/DECISIONS.md | Substantive design tradeoffs with rejected alternatives |
| docs/OPERATIONS.md | Run, inspect, back up, restore, diagnose, and reset owned demo state |
| docs/ACCEPTANCE.md | Requirement-to-test-to-evidence mapping |
| docs/BENCHMARKS.md | Workloads, actual measurements, interpretation, limitations |
| docs/CASE_STUDY.md | Problem, implementation, difficult defect, evidence, next steps |
| docs/THIRD_PARTY.md | Data/model/audio/code provenance and license notes |
| docs/AGENT_STATUS.md | Current phase, completed gates, active files, next concrete action |
| docs/SHARED_CHANGE_REQUESTS.md | Requests for coordinator-owned files |
| artifacts/ | Small checked-in sample outputs and manifests with source revision identifiers |
| README.md | Product-specific quick start and short demo narrative |

Adapt the module name pp_project to the exact package in Section 2. These paths are contracts, not a request for empty files. Add migrations/, templates/, Dockerfile, and compose.yaml only where needed.

### 3.3 Independent environments

Use a monorepo containing ten independent uv projects. Each project owns its pyproject.toml, uv.lock, and local .venv. Root tooling lives in tooling/quality/ with its own environment.

Do not make the ten products members of one uv workspace. uv workspaces share a lockfile and joint resolution, and their Python constraints interact; the official documentation recommends independent projects where separate environments or incompatible requirements are needed. This portfolio benefits from that separation because scientific dependencies, backend frameworks, and storage tools have different needs. [S02]

No project may require PYTHONPATH hacks, imports through another project's src directory, or an editable install of an unfinished sibling. Install and test the built distribution in a clean environment as a final packaging check.

### 3.4 Python and dependency baseline

Use standard, GIL-enabled CPython 3.13 as the initial compatibility floor and a supported, explicitly pinned patch release selected during bootstrap. Python 3.13 remains security-supported at this document's preparation date; it is not the newest Python release. [S01]

Evaluate CPython 3.14 during bootstrap. Use it as a project's default when that project's required dependencies install and its full checks pass. Record the actual default and the supported matrix in portfolio.toml. Keep a working 3.13 path for scientific projects if required wheels or dependencies constrain adoption. Test newer versions only where supported; do not require prereleases or experimental free-threaded builds.

All ten projects initially support CPython 3.13. Choosing 3.14 as a default does not remove that compatibility requirement. Record default_python, required_python_versions, and unsupported platform/interpreter combinations in portfolio.toml; package requires-python metadata must agree with the declared matrix.

Select stable, supported library releases from their official documentation during implementation. Commit exact resolutions in each uv.lock and record uv/interpreter versions. Do not guess patch versions from this brief. CI must check lock freshness and must not silently rewrite lockfiles; uv distinguishes --locked from --frozen, and --locked should enforce metadata consistency. [S03]

Recommended shared tools:

- pytest for tests and pytest-cov for coverage evidence.
- Hypothesis for generated invariants and state-machine testing.
- Ruff for formatting and linting.
- mypy with strict checking of the project's own core and public interfaces.
- Hatchling or another justified standards-compliant build backend.
- structlog or standard logging with structured fields for services.
- OpenTelemetry only where traces help diagnose concurrent or distributed behavior.
- Typer or argparse for CLI entry points.
- FastAPI and Pydantic for selected service boundaries; Django for Meridian.
- Matplotlib for reproducible scientific/benchmark figures.
- Markdown documentation; MkDocs may provide a root documentation build.

Do not force every project to use every tool.

---

## 4. Ten-agent execution protocol

### 4.1 Required team structure

The coordinator must attempt to run these ten specialist agents concurrently:

~~~text
A01 — Anchor / distributed workflow engineer
A02 — Strata / storage engine engineer
A03 — Current / stream-processing engineer
A04 — Meridian / backend and transactional-data engineer
A05 — Quarry / data platform engineer
A06 — PyTrace / compiler and developer-tools engineer
A07 — Atlas / search and information-retrieval engineer
A08 — Proving Ground / ML platform engineer
A09 — Routecraft / optimization engineer
A10 — Resonance / audio and numerical-computing engineer
~~~

A coordinator plus ten implementation agents requires eleven concurrent execution slots if the runtime counts the coordinator. Inspect the actual tool capacity. If fewer slots exist, retain all ten assignments and run the maximum supported number, queueing the others. State the real active count and capacity limit. Do not pretend that ten agents ran simultaneously, repeatedly spawn failing requests, or bypass runtime limits.

Agent concurrency and test-process concurrency are separate. Use a resource budget for compilation, data generation, database instances, and benchmarks. Keep heavy tests serialized or capped even when all ten agents can code at once.

### 4.2 Bootstrap before concurrent editing

The coordinator first:

1. Inspects repository contents, local changes, current branch, remote URL, and applicable AGENTS.md files.
2. Records the starting commit and preserves pre-existing user changes.
3. Establishes the root commands, portfolio.toml schema, directory ownership, Python defaults, and evidence format.
4. Creates the ten package directories with minimal valid packaging/configuration and project-specific ownership notes.
5. Creates the initial root CI checks and a working dispatcher; unimplemented projects must report incomplete, not pass.
6. Freezes shared contracts and sends every agent the full brief plus its assignment.
7. Launches all supported implementation agents. Do not finish one project before starting the next when parallel capacity is available.

Bootstrap is deliberately small. Do not spend the first phase building an internal platform while the ten actual projects remain empty.

### 4.3 Ownership rules during parallel coding

Each implementation agent may edit only its assigned projects/NN-name/ directory. Its own lockfile, migrations, documentation, and tests are inside that boundary. The coordinator owns every other path.

Agents may inspect sibling projects for interface context but must not edit them. To request a shared change, write docs/SHARED_CHANGE_REQUESTS.md inside the owned project and send a concise message containing:

~~~text
Request ID:
Requester:
Shared path:
Concrete proposed change:
Reason and affected command/API:
Compatibility impact:
Suggested verification:
~~~

The coordinator applies shared changes one at a time and announces any changed contract to all affected agents. An agent blocked on a shared improvement should continue work against the documented current contract or a local adapter within its own directory.

No worker may run git add, commit, checkout, switch, pull, merge, reset, clean, rebase, branch creation, or push. Concurrent agents sharing a checkout also share its index and branch. Ownership of files does not make concurrent Git mutations safe.

Workers may format only their own project. A project declaring a [tool.ruff] table must explicitly set extend = "../../ruff.toml" unless the coordinator documents an alternative; Ruff does not implicitly merge discovered child and parent configurations. Run validation in check mode on selected paths. [S27]

### 4.4 Single-main integration and commits

Work on main unless an existing repository rule prevents direct integration. Preserve branch protections and do not rewrite existing history. Do not create ten permanent agent branches.

The coordinator is the only Git writer:

1. Ask the relevant project owner to pause writes for a short handoff.
2. Review the exact changed paths and run the required checks on that stable snapshot.
3. Stage only explicit, reviewed paths. Never use a blanket staging command while unrelated agents are editing.
4. Commit a coherent slice with an accurate message; do not label scaffolding “complete.”
5. Resume the agent after the stable slice is committed.
6. At a global integration checkpoint, pause all relevant writers and validate the full selected snapshot.
7. Fetch and inspect remote changes before synchronizing. Push through the normal authenticated mechanism only within the executing user's authorization.
8. If the remote advanced, preserve both histories and inspect conflicts; do not force-push or repeatedly retry a rejected push without diagnosis.

Fetching and inspecting remote metadata may happen during project work. Before a merge, pull, or any remote reconciliation that changes the shared checkout, pause all checkout writers. Preserve outstanding owned work in coherent commits or verified snapshots, and preserve pre-existing user changes separately. Do not use automatic stashing, resets, or blanket staging to sweep up unrelated work. Resume workers only after reconciliation and ownership checks are complete.

If the executing environment requires separate checkouts, use isolated working copies with the same explicit path ownership and let the coordinator import reviewed changes into main. Do not let multiple workers mutate the same Git index through different paths.

This brief requests code implementation and integration. Normal commits belong to the delivery workflow. Do not assume separate authorization for public package releases, deployments, account changes, messages, or other actions outside that scope.

### 4.5 Shared agent kickoff contract

Send the following instruction to each of A01–A10, replacing the fields with Section 2:

~~~text
You are [AGENT_ID], the implementation owner of [PROJECT_NAME].
Work only under [OWNED_DIRECTORY].
Read the whole master brief, the common standards, and your project section.
Implement the original core, usable interfaces, all acceptance IDs, seeded
benchmarks, and project documentation. You own your package and uv.lock.
Do not mutate Git or coordinator-owned files.
Do not replace required behavior with mocks, wrappers, or generated stubs.
Keep docs/AGENT_STATUS.md current with exact commands, results, and blockers.
Request shared changes through your local SHARED_CHANGE_REQUESTS.md.
After each runnable milestone, send the coordinator a concise handoff.
Continue through failing acceptance tests and review corrections.
Finish with an evidence-backed handoff; do not declare verified completion
based only on tests you wrote against your own implementation.
~~~

Every project section below is a concrete agent assignment. The coordinator must include it in that worker's initial task rather than asking the worker to invent its own project.

### 4.6 Progress, review, and handoff

Use these status values consistently:

| Status | Meaning |
| --- | --- |
| queued | Assignment exists; no active worker yet |
| building | Implementation underway; required gates remain |
| runnable | A real end-to-end slice works |
| verifying | Full contract and failure scenarios are being checked |
| needs-fix | A specific check or independent review failed |
| blocked | A required step has a named external dependency or missing capability |
| complete | All local required gates and coordinator review have passed |

A status record includes the requirement IDs completed, the precise failing/blocked IDs, verified commands, artifact paths, and the next action. Percentages are optional and must be derived from weighted, completed gates; do not guess “90% done” from files or lines of code.

A final agent handoff includes:

- The actual implementation and its public interfaces.
- The required acceptance IDs and the evidence for each.
- Test, benchmark, and packaging commands with exit status and environment.
- The most serious defect found and how the regression test demonstrates the fix.
- Known limits, unsupported cases, and optional work left out.
- Shared-file requests and any integration risks.

---

## 5. Engineering standards for all projects

### 5.1 Architecture and Python quality

Keep domain and algorithm code callable without starting a web server or UI. Put persistence and networking behind narrow interfaces where substitution is useful. Avoid abstract factories, repositories, plugin managers, and dependency injection layers that have only one trivial use.

Use type annotations on public interfaces and core data structures. Prefer dataclasses, enums, immutable value objects, Protocols, and explicit exceptions when they clarify invariants. Constrain Any to documented third-party boundaries. Do not bypass typing with broad ignores. Type hints do not perform runtime input validation; validate untrusted input at the boundary. [S04]

Use iterators, generators, context managers, and efficient collection choices appropriately. Profile before applying optimization. Do not move the essential algorithms into Rust/C++ merely to avoid implementing them in Python; optimized numerical libraries are appropriate for array kernels.

Use structured concurrency, bounded queues, timeouts, explicit cancellation, and resource cleanup where needed. In asyncio code, preserve cancellation semantics and avoid swallowing CancelledError. CPU-bound loops must not block a service event loop. Select vectorization or processes deliberately, with measured costs and reproducible worker configuration. [S05]

Persisted formats need a format/schema version and a documented compatibility policy. Do not assume pickle is a safe format for externally supplied files or stable interoperability.

### 5.2 Failure semantics and claims

Define the precise boundary of each guarantee.

- “Durable” identifies what was acknowledged, which persistence operation occurred, and what failures were tested.
- “Exactly once” identifies the input identity, checkpoint boundary, and sink transaction or deduplication contract.
- “Deterministic” identifies seeded algorithms, tie-breaking, environment constraints, and floating-point tolerance.
- “Serializable” requires a design and test model that actually provides serializability.
- “Real time” requires measured latency and a specified runtime; Resonance's required processing mode is offline.
- “Secure” is not a blanket completion claim; describe implemented controls and remaining assumptions.

A process-kill test does not simulate every power-loss or storage-device failure. A passing mock test does not verify database isolation. A benchmark on synthetic data does not demonstrate production capacity. State those distinctions in the case studies.

### 5.3 Testing that reveals real defects

Every project needs:

1. Unit tests for core rules with independently derived expected values.
2. Integration tests using the actual required persistence/process boundary.
3. At least one nontrivial property or state-machine suite for its core behavior.
4. An acceptance demonstration that drives the same public interface a user would use.
5. A negative/failure suite tied to realistic defects, not only malformed JSON.
6. A clean wheel installation test from outside the source tree.

Use the src layout and pytest importlib mode to help prevent accidental imports from the checkout. Verify actual installation, not a PYTHONPATH workaround. [S06]

Hypothesis stateful tests are suitable for generating action sequences against a simpler reference model. Use them for storage histories, ledger actions, workflow transitions, or other stateful contracts; preserve minimal failing examples as readable regression cases where valuable. [S07]

Never derive the expected answer by calling the same algorithm under test. A feasibility checker must recompute constraints; a storage model must not reuse the production lookup code; a query relevance oracle must not reuse its scorer.

Use coverage as supporting evidence. Aim for at least 85% branch coverage in each project's defined own-code core, and 90% where practical for the ledger/storage state machines. Measure and report the actual scope. A numeric target does not replace all acceptance gates, and trivial tests added to inflate coverage are unacceptable. Do not impose exhaustive testing on wrappers or generated migration boilerplate.

Required tests must not use permissive continue-on-error, empty assertions, unconditional skips, or xfails to hide broken behavior. Optional dependencies may be excluded from their optional matrix, with the exclusion visible.

### 5.4 Service and data boundaries

For exposed APIs, require request validation, bounded request sizes, consistent error responses, pagination where collections grow, deterministic test fixtures, and explicit authentication behavior. Use established framework authentication rather than custom cryptographic designs.

Meridian and Atlas must test cross-tenant isolation. Local demonstration services bind to loopback by default. Include health and readiness endpoints only where their meanings are distinct and implementable.

Do not log credentials, full private documents, or sensitive records. Keep demo tokens visibly local and synthetic. Process only caller-selected files and owned test directories; path traversal and accidental overwrite tests are required for file-accepting tools.

Migrations and reset commands must name their target environment. A demo reset may remove only data it created and must never issue a global Docker prune or delete arbitrary files.

### 5.5 Reproducible benchmarks

Every benchmark result must contain:

~~~json
{
  "schema_version": 1,
  "project": "project-slug",
  "source_commit": "actual-tested-commit",
  "source_dirty": false,
  "source_scope": "project-or-integration-or-repository",
  "source_content_sha256": "actual-tested-source-digest",
  "root_contract_sha256": "actual-relevant-root-input-digest",
  "lockfile_sha256": "actual-lockfile-hash",
  "python": "actual-version",
  "os": "actual-operating-system",
  "cpu": "actual-model-or-documented-unknown",
  "memory_limit_bytes": null,
  "seed": 1729,
  "dataset_id": "actual-generator-and-input-hash",
  "profile": "ci-or-standard",
  "parameters": {},
  "warmup_runs": 1,
  "measurement_runs": 5,
  "metrics": {},
  "correctness_checks": {},
  "status": "passed-or-failed-or-blocked"
}
~~~

This is a schema example, not measured data. Replace example strings with real values. Use null with an explanation for genuinely unavailable environment metadata.

The **ci** profile is a small deterministic correctness workload with generous resource bounds. The **standard** profile evaluates a meaningful larger dataset locally. Optional stress profiles must be explicitly invoked.

Record latency distributions, throughput, memory, correctness, and domain-specific metrics where relevant. Separate cold start from warm performance; record I/O durability settings, process counts, thread counts, and cache state. Use at least five measured repetitions for timing comparisons unless run cost demands a documented alternative.

Do not set arbitrary “one million requests per second” targets. Workload sizes in this brief are test inputs, not promised speeds. Establish a first truthful baseline, identify bottlenecks, and document measured improvements. A slower algorithm that provides a stronger guarantee must be compared under that same guarantee.

Pin scientific-library thread counts for benchmark comparisons so ten parallel agents do not distort measurements. Run standard benchmarks under an exclusive resource lease.

### 5.6 Evidence source revisions

Separate code verification from the commit that later adds its report. A test report records the code commit it actually tested; adding that report creates a later commit. Do not pretend that a report can include its own future commit hash.

For development snapshots before a commit, record a dirty-state flag and source-content digest. Final release-quality evidence must point to a committed source snapshot. The final repository handoff records the final integration commit separately.

Capture the source revision before execution and confirm its digest afterward. Project verification includes its code, dependencies, tests, fixtures, and relevant root command/configuration inputs. Define the digest input list explicitly; exclude generated reports/results to avoid self-reference. Label evidence scope as project, integration, or full repository. Final committed evidence runs from a clean exported copy of the named commit or an equivalent immutable verification checkout. Changed code, tests, locks, or relevant root tooling invalidate affected evidence; adding an unchanged-source report does not. Establish the final committed source snapshot with implementation writers paused.

Do not check in virtual environments, full datasets, caches, model checkpoints, large database files, or bulk benchmark logs. Keep small sample outputs and generator/configuration files in Git. Store large run outputs as CI artifacts or local ignored results with provenance.

---

## 6. Common commands, CI, and global delivery gates

### 6.1 Cross-platform task interface

The coordinator must implement these commands in scripts/portfolio.py:

~~~text
python scripts/portfolio.py list
python scripts/portfolio.py doctor
python scripts/portfolio.py setup anchor
python scripts/portfolio.py check anchor
python scripts/portfolio.py demo anchor
python scripts/portfolio.py benchmark anchor --profile ci
python scripts/portfolio.py benchmark anchor --profile standard
python scripts/portfolio.py clean-demo anchor
python scripts/portfolio.py verify-all --jobs 2
python scripts/portfolio.py docs
~~~

Accept all ten project slugs from portfolio.toml. Use pathlib and subprocess argument lists rather than shell string concatenation. Set the working directory to the selected project explicitly. Keep exit codes intact and print the command that failed.

The setup command resolves nothing silently in CI: initial development creates the lock; repeatable installation uses it with a freshness check. The check command runs format validation, lint, type checking, tests, and a build/install smoke check according to the project's manifest. Missing required services produce an explicit blocked/nonzero result.

The demo command creates isolated seeded state, runs the actual product, writes a small report, and gives a human-readable result. Starting a web server alone is not a successful demo.

Use an executable timeout and cleanup on subprocesses. No command may leave orphan workers after failure. Linux is the required platform for low-level storage durability and service fault suites; pure-Python installation and CLI checks should also run on Windows and macOS. Clearly list any platform boundary rather than claiming universal support.

### 6.2 Project manifest and ports

portfolio.toml is coordinator-owned and lists each project's slug, directory, distribution/import/CLI names, default Python, required services, test commands, supported platforms, and demo entry point.

Include required_python_versions explicitly. CI expands project entries into the required interpreter jobs and selects each job's interpreter explicitly rather than accidentally inheriting .python-version. Include thread/process counts in benchmark parameters.

Default HTTP demonstration ports, where a project needs one:

| Project | Port |
| --- | --- |
| Anchor | 8101 |
| Current | 8103 |
| Meridian | 8104 |
| Atlas | 8107 |
| Proving Ground | 8108 |
| Routecraft optional viewer | 8109 |
| Resonance optional viewer | 8110 |

Ports are configurable. Strata, Quarry, and PyTrace are CLI/library-first and need no server.

A project-specific PostgreSQL instance must have a unique Compose project name and database/user namespace. Prefer ephemeral host port allocation or configurable bindings; tests must never assume a sibling project's database is their own.

### 6.3 CI workflow behavior

Create an actual ten-project matrix. GitHub Actions supports generating job variations from a matrix; use project metadata as the source of truth. [S08]

For every relevant change:

- Run root metadata/command checks.
- Detect changed projects; shared tooling or contract changes select all affected projects.
- Validate each selected project's lock, lint, types, tests, packaging, and ci demo.
- Use the real PostgreSQL service for Anchor and Meridian integration tests.
- Produce small machine-readable test/evidence artifacts.
- Include an aggregate status that fails when any required job fails or is unexpectedly absent.
- Limit simultaneous heavy jobs to the available CI budget.
- Validate documentation links and local artifact references.

Set ordinary workflow permissions to contents: read. Pin third-party Actions to reviewed full commit SHAs and document their release tags alongside them. Do not interpolate untrusted issue/PR text into shell commands or run fork code with privileged secrets. These practices follow GitHub's secure-use guidance. [S09]

Test changed-project selection for added, modified, deleted, and renamed paths; root/workflow changes; and an unavailable comparison base. If a trustworthy diff is unavailable, run the full required matrix. Manifest validation requires all ten identities. The aggregate job distinguishes an intentionally empty selection from a failed selector or an unexpectedly missing required job.

The extended workflow should be manually runnable and exercise the full matrix, longer stateful/fault suites, clean install, and standard benchmarks where the runner can support them. Do not assume scheduled runs, paid minutes, or deployment infrastructure have been authorized. CI screenshots or badges may report only real workflows and actual states.

### 6.4 Global gates

| Gate | Requirement |
| --- | --- |
| G01 | All ten projects contain a substantial, identifiable original Python core |
| G02 | Each project installs independently from a fresh checkout using its committed lock |
| G03 | Every required project acceptance ID passes on its declared platform |
| G04 | All required lint/type/test/build checks pass without hidden exceptions |
| G05 | Every demo exercises real implementation and has a reproducible seed/input |
| G06 | Correctness/failure tests use independent oracles and real system boundaries |
| G07 | Benchmarks contain actual measurements and source/environment provenance |
| G08 | Documentation links commands, architecture, evidence, and known limitations |
| G09 | At least the three specified cross-project demonstrations pass |
| G10 | Root CI selects projects correctly and its aggregate status reflects failures |
| G11 | A reviewer can understand the portfolio and run a flagship demo quickly |
| G12 | Final integration is reviewed, committed, and its remote status reported accurately |

A blocked gate stays blocked. Local success and remote CI success are separate facts. A finished README cannot close a failing gate.

---

## 7. A01 — Anchor: durable workflow engine

**Owner:** A01  
**Path:** projects/01-anchor/  
**Package:** pp_anchor  
**Primary interface:** Python SDK, CLI, and local HTTP control API  
**Product objective:** Coordinate long-running work that survives process failure and can explain every state transition.

### 7.1 What to build

Build a durable workflow runtime with versioned definitions, an append-only event history, persisted timers, signals, parallel activities, bounded retries, worker leases, cancellation, and compensation.

The reference application exports a synthetic dataset: validate a request, fetch several partitions concurrently, create an archive, wait for an approval signal, and publish it to a local idempotent provider. A deliberately failed stage triggers cleanup. The user must see a worker die and the workflow recover.

Implement a small explicit workflow language in Python using a deterministic reducer:

~~~python
def decide(state: WorkflowState, event: HistoryEvent) -> list[Command]:
    ...
~~~

The public SDK may provide a typed builder for sequences, parallel groups, timers, and signal waits. Required commands are ScheduleActivity, StartTimer, AwaitSignal, Join, Complete, Fail, and Compensate. Persist external results as history events. Do not attempt to serialize arbitrary suspended Python call stacks.

Temporal's documentation is a reference for why replayable workflow commands need deterministic behavior and why external operations belong outside the replay path. Anchor implements its own bounded model rather than reproducing Temporal's entire product. [S10]

### 7.2 Stack and module ownership

Use asyncio, dataclasses/Protocols, PostgreSQL, psycopg 3, FastAPI, Pydantic, Typer, pytest, and Hypothesis. Keep SQL migrations and query definitions visible for review.

| Module under src/pp_anchor/ | Required implementation |
| --- | --- |
| definitions/, sdk/ | Versioned definitions, typed commands, builder validation, stable definition digest |
| history/, replay/ | Ordered events, reducer invocation, replay reconstruction, divergence diagnostics |
| scheduler/ | Ready work, persisted timers, retry policy, joins, bounded admission |
| workers/ | Activity registry, concurrent execution, heartbeat, lease epochs, cancellation |
| persistence/ | Transactions, migrations, durable projections, unique constraints |
| api/ | Submission, signal, cancel, status, history, readiness |
| cli/ | Submit, inspect, replay, start scheduler/worker, run demo |
| observability/ | Structured transition records and useful queue/retry/lease metrics |

Tables include workflow_runs, history_events, activity_tasks, activity_attempts, timers, signals, and ingress_requests. Key fields include workflow_id, definition_version/digest, event_seq, command_id, attempt_number, lease_epoch, lease_expiry, canonical_request_hash, and terminal_status.

The first useful files should be definitions/commands.py, history/events.py, replay/reducer.py, and a small independent reference-state test. Add the database adapter after the core transition contract is explicit.

### 7.3 Interfaces and invariants

Required HTTP operations:

~~~text
POST /runs
POST /runs/{run_id}/signals
POST /runs/{run_id}/cancel
GET  /runs/{run_id}
GET  /runs/{run_id}/history
GET  /health
GET  /ready
~~~

Submission and signals use idempotency keys. A duplicate key with the same canonical payload returns the original result; the same key with a different payload fails with a clear conflict.

History append and resulting durable task/timer creation occur in one transaction. Each run has one monotonic event sequence. Stable command IDs prevent duplicate logical scheduling. Every run pins its definition version.

Activity execution is at least once. Reclaiming a lease increments an epoch; completion and heartbeat updates must compare that epoch transactionally. A stale worker cannot change engine state. External side effects require their own idempotency contract, with a stable business key retained across retries.

Queue selection may use FOR UPDATE SKIP LOCKED, but the lease/state transition is protected by actual constraints and transactions. PostgreSQL documents SKIP LOCKED for queue-like consumption; it is not a universal consistent-read mechanism. [S11]

Use database time for persisted lease/deadline comparisons and an injectable clock abstraction for tests. Do not use local worker wall clocks as an unexamined authority. Record retry backoff and any jitter decisions that affect replay. Waiting timers belong in durable storage; do not allocate one permanently suspended coroutine for every future timer.

Compensation has its own pending/running/failed/completed state. A failed cleanup cannot be reported as successfully compensated.

Cancellation does not guarantee an in-flight external effect has stopped. The synthetic provider must persist a terminal cancellation/cleanup record or equivalent provider-side fence that rejects a late publication after compensation. Report full compensation only under that demonstrated provider contract. Test an activity paused before publication, cancellation and cleanup, then the stale activity resuming; it must not recreate the cleaned-up effect.

### 7.4 Implementation sequence

1. Build the pure state machine and versioned command/event schema.
2. Implement replay and deliberate divergence cases.
3. Implement PostgreSQL transaction boundaries and idempotent ingress.
4. Add two-scheduler-safe task claiming, worker leases, and stale-epoch rejection.
5. Add retry/timer/signal/join/cancellation behavior.
6. Add compensation and the idempotent synthetic provider.
7. Expose CLI/API inspection and the failure demonstration.
8. Verify failure suites, profile queue behavior, and write the case study.

### 7.5 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| AN-01 | Replay every demo history to the same final state and command IDs; an incompatible definition identifies the divergence event |
| AN-02 | Crash submission before/after database commit, retry, and prove one logical run with consistent idempotency conflict handling |
| AN-03 | Kill a worker after the provider effect but before completion acknowledgement; execution retries and the provider records one logical publication |
| AN-04 | Pause worker A beyond its lease, let worker B take over, resume A, and reject all stale-epoch state changes |
| AN-05 | Stop schedulers with persisted timers, advance the test clock, restart, and record one logical firing per timer |
| AN-06 | Exercise early/duplicate signals, completion/cancellation races, a paused-before-effect stale activity after cleanup, and all completion orders of a parallel join |
| AN-07 | Fail a later stage and a compensation attempt; show retries and an unresolved state until cleanup actually succeeds |
| AN-08 | Run two schedulers and several workers with injected failures; account for every accepted run and verify no silent loss or orphan activity |

### 7.6 Demo and benchmark contract

The root demo command must display the timeline of a real export, a worker failure, a resumed activity, one provider publication, and replay verification. Write a JSON history summary and a readable timeline.

Use 100 workflows with five short activities for ci. Use 5,000 workflows with five activities, two schedulers, and configurable worker concurrency for standard. Separately evaluate 100,000 future timers to expose memory behavior. Report throughput, ready-to-start delay, queue depth, retries, database size, recovery time, and engine memory. Benchmark offered load and completed load separately.

**Optional extensions:** cron schedules, child workflows, a small visual inspector.  
**Excluded:** arbitrary-code sandboxing, multi-region consensus, general in-flight workflow migration, universal exactly-once effects, and a large visual editor.

---

## 8. A02 — Strata: transactional embedded storage engine

**Owner:** A02  
**Path:** projects/02-strata/  
**Package:** pp_strata  
**Primary interface:** embedded Python library and inspection CLI  
**Product objective:** Store versioned byte records with atomic transactions, predictable snapshot reads, and verified recovery.

### 8.1 What to build

Implement an LSM-style key-value engine with an original ordered memtable, write-ahead log, immutable sorted tables, Bloom filters, sparse indexes, version manifests, snapshot-isolated transactions, and compaction.

The concurrency boundary is one database-owning process, multiple readers within that process, and serialized commit publication. A second database-owning process fails explicitly. Read/write transactions use first-committer-wins checks for their write sets. Do not claim serializability.

LevelDB's implementation notes are an architectural reference for tables, manifests, compaction, and recovery. Cite this influence and document Strata's own format and simpler boundaries. [S12]

### 8.2 Stack and module ownership

Use Python file APIs, struct, memoryview, heapq, a stable hash, threading where justified, and mmap only if profiling supports it. Implement the storage machinery; SQLite may be a comparative baseline, never the core.

| Module under src/pp_strata/ | Required implementation |
| --- | --- |
| codec/ | Bounded binary parsing, versioned headers, checksums, size limits |
| wal/ | Complete transaction frames, append/sync, rotation, replay |
| memtable/ | Original ordered structure, such as a bounded skip list; immutable flush view |
| sstable/ | Sorted blocks, sparse indexes, Bloom filters, block iteration |
| transactions/ | Snapshot sequences, buffered writes, commit conflict detection |
| versions/, manifest/ | File-set publication, live sequence tracking, metadata |
| compaction/ | Merge planner, obsolete-version handling, safe tombstone removal |
| recovery/, diagnostics/ | Open/recover, verify, inspect, injected filesystem failure points |
| api.py, cli.py | Database/transaction interface and operator commands |

Initial files: codec/records.py, wal/frames.py, transactions/model.py, and a separately implemented versioned dictionary oracle.

### 8.3 Data and algorithm contracts

Keys and values are bytes. Set explicit limits, initially 4 KiB keys, 1 MiB values, and 16 MiB transaction batches. Reject malformed lengths before allocating memory.

Internal records contain user_key, commit_sequence, record_type, and value. A WAL frame represents one complete transaction batch with length, checksum, and sequence. SSTables contain format identifiers, checksummed blocks, key ranges, and indexes.

Required public behavior:

~~~python
with Database.open(path, durability="sync") as db:
    with db.begin() as tx:
        tx.put(b"account:a", b"120")
        tx.put(b"account:b", b"80")

    with db.snapshot() as snapshot:
        value = snapshot.get(b"account:a")
        rows = list(snapshot.scan(start=b"account:", stop=b"account;"))
~~~

Specify whether normal context-manager exit commits or only closes, and test exceptions. Prefer explicit documented semantics over copying this illustrative syntax blindly.

Transactions expose get and scan as repeatable snapshot reads overlaid with their private write set. Test read-your-writes, private deletes, repeated changes to one key, scans including private mutations, and an aborted transaction exposing no writes.

Use stable hashing for persistent Bloom filters. Python's per-process hash randomization must not define an on-disk format. Include fixed test vectors for format encodings and hash behavior.

A committed sequence makes an entire batch visible at once. Durable acknowledgement follows successful WAL synchronization. If synchronization fails after an append, report the failure without claiming success; recovery may find an unacknowledged complete transaction. State that ambiguity explicitly.

After an append/sync failure leaves WAL state uncertain, put the writer in an explicit failed state and reject further writes until close and successful recovery. Document which reads remain available. Online repair is optional and requires proof of a valid log boundary/sequence before resuming writes.

Retain versions required by active snapshots. Hold file references for iterators during compaction. Drop tombstones only when older values cannot reappear. Keep enough conflict metadata to detect a key changed after an old transaction began, including insert-then-delete cycles.

Publish new tables and the durable manifest before retiring their source files. Define POSIX filesystem/synchronization assumptions. Process termination, short writes, reordering simulation, and sync failures exercise different parts of the durability contract; SQLite's crash-testing discussion is a useful reference for this distinction. [S13]

### 8.4 Implementation sequence

1. Specify and test byte formats and independent reference behavior.
2. Implement durable WAL batches and recovery before adding compaction.
3. Add ordered memtables and sorted-table reads/scans.
4. Add atomic sequence publication and snapshot transactions.
5. Add write-conflict checks and snapshot lifetime tracking.
6. Add compaction with pinned versions/files and safe tombstones.
7. Add failure injection, diagnostics, and backup/restore of a consistent snapshot.
8. Measure reads, batches, recovery, and amplification; document observed bottlenecks.

### 8.5 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| ST-01 | Compare seeded operations and range scans against an independent versioned reference model |
| ST-02 | Interrupt at WAL append/sync/publication points; retain every acknowledged transaction and never expose a partial batch |
| ST-03 | Distinguish an incomplete final WAL frame from interior corruption; never silently discard later committed data |
| ST-04 | Hold snapshots across overwrite/delete/flush/compaction and preserve their original point-read and scan results |
| ST-05 | Reject conflicting writers, including an old transaction racing with insert-then-delete on its written key |
| ST-06 | Demonstrate allowed snapshot-isolation write skew and explain why it is not a serializable database |
| ST-07 | Interrupt table creation, manifest publication, and obsolete-file cleanup; recover without resurrecting deleted keys |
| ST-08 | Handle disk-full, short-write, failed-sync, oversize input, malformed length, second-process open, and snapshot backup/restore; reject writes after uncertain WAL failure and recover without sequence reuse |

### 8.6 Demo and benchmark contract

The demo has two sequential phases. First, one owner process writes a versioned catalog and retains an old snapshot through overwrites, deletes, and compaction, then closes all handles. Second, a subprocess becomes the sole owner, performs acknowledged transactions, and is terminated at a controlled failpoint. Another process reopens and verifies recovered data and new snapshots. Ordinary in-memory snapshot handles do not survive owner-process termination.

ci uses 2,000 records plus bounded fault/property sequences. The extended stateful suite uses at least 100 seeds of 5,000 mixed operations. Standard uses 250,000 initial records with 16-byte keys and 256-byte values, followed by 200,000 mixed operations and a separate churn profile.

Compare durable single commits and durable batches of 100 separately. Record read/write latency, recovery time, memory, disk usage, cache settings, compaction stalls, and read/write/space amplification. Compare SQLite only under explicitly equivalent durability and transaction settings.

**Optional extensions:** compression, additional compaction policies, a read-only snapshot file format.  
**Excluded:** SQL, networking, replication, distributed transactions, arbitrary object persistence, and unsupported cross-platform power-loss claims.

---

## 9. A03 — Current: event-time stream processor

**Owner:** A03  
**Path:** projects/03-current/  
**Package:** pp_current  
**Primary interface:** Python pipeline API and CLI; a small metrics API is optional  
**Product objective:** Produce correct time-based results from delayed and out-of-order events while bounding state and recovering consistently.

### 9.1 What to build

Build a local event-time runtime with keyed workers, map/filter, tumbling and sliding aggregation windows, one bounded interval join, explicit watermarks, allowed lateness, late-event reporting, backpressure, and consistent checkpoints.

Use a fixed worker/partition count for a run. Implement the time and state algorithms in Python; use SQLite as the durable ingress/checkpoint/catalog adapter. Do not depend on Strata or a message broker.

The demo processes device readings and metadata. One source pauses, another runs ahead, delayed records arrive, and the process fails near a checkpoint. Final committed output must match an independent batch oracle over the same accepted event/control trace.

### 9.2 Stack and module ownership

Use asyncio, typed records and Protocols, heapq, SQLite, Typer, pytest, and Hypothesis. Put blocking persistence work behind a bounded writer mechanism that does not block the event loop indefinitely.

| Module under src/pp_current/ | Required implementation |
| --- | --- |
| model/, sources/ | Versioned event envelope, replayable NDJSON input, source protocol |
| ingress/ | Durable ingress ordinals, event/control ordering, input acknowledgement |
| runtime/ | Stable key routing, bounded queues, worker lifecycle, backpressure |
| event_time/ | Per-input watermarks, minimum progress, idle/resume decisions |
| operators/ | Window state, aggregates, interval joins, expiration |
| checkpoints/ | Coordinated barriers, staged state, atomic checkpoint publication |
| sinks/ | Local transactional output and a tested idempotent external sink |
| cli/, diagnostics/ | Run, inspect, replay, trace event disposition and checkpoint state |

Begin with model/envelope.py, event_time/policy.py, operators/tumbling.py, and an independent batch oracle. Progress to recovery only after window boundary rules are executable.

### 9.3 Event and checkpoint contracts

An event contains source_id, partition, source_offset, event_id, event_time, schema_version, key, payload, and durable ingress_ordinal. Control records include watermark, idle, resume, and end-of-input.

Use integer milliseconds or microseconds consistently, and half-open windows [start, end). State whether an event exactly on a lateness boundary is accepted. Implement sum/count/min/max, an average derived from sum/count, and deterministic tie-breaking where needed.

Journal event/control ordering, including idle/resume decisions. Source offsets alone cannot reproduce a previous interleaving or lateness decision. Stable partition hashing and recorded ordering must make replay of the same trace reproducible.

The tuple (source_id, partition, source_offset) identifies admission. The first committed admission assigns a durable ingress ordinal; same-payload retries return that admission, and conflicting payload reuse fails. Acknowledge only after the ingress transaction commits. Include a crash after commit and before acknowledgement.

Per-input and operator watermarks never regress. The minimum active input watermark governs progress; idle inputs are explicitly excluded, and resumed old records follow the chosen late policy. These concerns are explained in Flink's event-time documentation. [S14]

A checkpoint records processed ingress positions, input watermarks, idle state, operator/window/join state, schema/code versions, and pending outputs. Commit a consistent prefix. Late updates to an existing window use a stable logical result key plus monotonic revision; downstream upsert semantics must be explicit.

The local transactional sink publishes state/checkpoint/output coherently. A supported external sink uses an idempotent logical output key. Physical reprocessing during recovery is allowed; exactly-once observable results require the stated source and sink contract. [S15]

Identify deliveries by (job_id, operator_id, logical_result_key, revision). Retrying a revision must preserve its canonical payload; conflicting reuse fails. Persist the delivery key/payload with checkpoint or outbox state. The sink retains the greatest committed revision per result key, so a delayed older retry cannot overwrite a newer revision.

Do not confuse event-id duplicates with source-offset replay. Distinct offsets with the same event ID remain distinct inputs unless a separately specified deduplication operator is enabled.

Bound join retention and define expiration. A late event cannot recreate expired state silently. Hold input or fail explicitly when memory/disk budgets are reached; never silently drop accepted input to preserve a throughput number.

### 9.4 Implementation sequence

1. Define envelopes, windows, timestamp units, lateness, and independent oracles.
2. Implement single-worker operators and property tests.
3. Add stable key partitioning and bounded async execution.
4. Add durable ingress and recorded time/control decisions.
5. Implement consistent barriers, checkpoint publication, and restoration.
6. Add sink idempotency, idle/resume, late revisions, and resource controls.
7. Build the failure demonstration and event-disposition report.
8. Profile normal, hot-key, stalled-source, and stalled-sink workloads.

### 9.5 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| CU-01 | Independently derive admission/disposition from the raw journaled event/control trace and compare both dispositions and finalized windows/joins |
| CU-02 | Test exact window/join boundaries, empty keys, repeated timestamps, multiple join matches, and supported negative time behavior |
| CU-03 | Distinguish on-time, accepted-late, and rejected-late inputs; preserve revision rules and avoid state resurrection |
| CU-04 | Stall, mark idle, advance, and resume a source with old records without regressing watermarks |
| CU-05 | Interrupt before/during/after checkpoint staging and publication; restore only a complete consistent checkpoint |
| CU-06 | Lose sink acknowledgement, retry revisions, publish revision 2 before retrying revision 1, and preserve revision 2; reject conflicting reuse of a delivery ID |
| CU-07 | Stall the sink and inject a 50%-hot key; enforce buffer/disk limits and observable backpressure |
| CU-08 | Prevent double application of replayed offsets, document repeated event IDs, and reject incompatible checkpoint/code versions |

### 9.6 Demo and benchmark contract

ci uses 10,000 generated events across four source partitions. Standard uses one million approximately 256-byte events, 10,000 keys, 10% out-of-order arrivals, an idle interval, and a separate hot-key run. Use 30-second windows, explicit lateness, and a configurable checkpoint interval, initially every 10,000 events.

Report throughput, event disposition counts, watermark lag, finalization latency, checkpoint duration, restore time, buffer peaks, operator state size, and memory. Reconcile input counts with accepted/rejected/replayed categories.

**Optional extensions:** session windows, a Kafka source adapter, a small operator inspector.  
**Excluded:** network-distributed execution, dynamic rescaling, unbounded joins, a general SQL planner, and exactly-once effects for arbitrary HTTP endpoints.

---

## 10. A04 — Meridian: multi-tenant ledger and reconciliation backend

**Owner:** A04  
**Path:** projects/04-meridian/  
**Package:** pp_meridian  
**Primary interface:** authenticated Django API, operator CLI, and focused Django views  
**Product objective:** Maintain correct, auditable simulated accounting records under concurrency and reconcile them with imported statements.

### 10.1 What to build

Build a double-entry journal service with accounts, immutable posted journals, reversals, idempotent posting, replayable balance projections, historical balances, statement imports, and reviewable reconciliation proposals.

Use multiple synthetic tenants and currencies. Every journal belongs to one tenant and one currency. Support multiple currencies using separate currency-specific accounts and same-currency journals; a business/customer may own several such accounts. Foreign-exchange accounting and actual payment execution are outside scope.

The demonstration is a fictional equipment-rental business receiving simulated invoices, payments, refunds, and statement rows. Show a duplicate submission, a reversal, an ambiguous statement match, a concurrent transfer, and a balance rebuild.

### 10.2 Stack and module ownership

Use Django 5.2 LTS at a verified supported patch, Django REST Framework where useful, PostgreSQL, psycopg 3, pytest-django, Hypothesis, and factory/fixture helpers only where they reduce duplication. Django 5.2 is an LTS release and supports the selected Python families at appropriate patch levels. [S16]

| Module under src/pp_meridian/ | Required implementation |
| --- | --- |
| domain/money.py | Strict decimal-string parsing, integer minor units, amount bounds, allocation |
| domain/journal.py | Account/posting/journal values, validation, reversal construction |
| domain/replay.py | Independent balance/trial-balance reconstruction from immutable postings |
| reconciliation/normalize.py | Statement identity, signed direction, timestamps, reference normalization |
| reconciliation/candidates.py | Sparse graph using amount/currency/reference/date features |
| reconciliation/assignment.py | Original bounded minimum-cost matching and ambiguity detection |
| application/ | Posting, reversal, import, reconciliation, approval use cases |
| persistence/ | Django models, constraints, migrations, transactional repositories |
| api/, config/, management/ | Authenticated routes, settings, migrations, seed/audit/replay/demo |
| templates/ | Focused journal, account history, and reconciliation review screens |

Keep domain and matching code importable without initializing Django. Start with money.py, journal.py, and tests demonstrating exact allocation and journal conservation.

### 10.3 Domain, database, and API contracts

Represent amounts in bounded integer minor units. Accept canonical decimal strings at the API and reject floats, NaN/infinity, excessive decimal precision, unsupported currencies, and overflow.

A posted journal contains at least two nonzero postings; signed amounts sum to zero; account, tenant, and currency constraints agree. Account currency cannot change after use. Corrections create linked reversal journals. The required baseline allows one full reversal; partial reversals are optional.

Implement largest-remainder allocation in Python, with stable tie-breaking. For negative totals, define and test the sign policy. Allocating one cent among several recipients must still conserve one cent.

Use a unique tenant/idempotency key plus canonical payload hash. Journals, postings, balance projections, and the idempotent result commit atomically. Use explicit row-lock ordering and a documented PostgreSQL isolation policy, with bounded retries of the entire transaction on serialization failure. Django atomic() alone is not a statement that an application is serializable. [S17]

Enforce tenant/account/journal/currency referential consistency and posted-data immutability in PostgreSQL. Enforce verified end-user membership in every application use case and API/read/export path. If claiming database-enforced user authorization, add transaction-local principal context and tested RLS policies under the actual non-owner application role. A per-row CHECK cannot enforce an arbitrary cross-row posting sum; implement and test a reviewed deferred constraint trigger or an equivalently enforceable transactional design. Do not rely exclusively on serializer validation.

For historical as_of_sequence queries, allocate a tenant sequence while holding the tenant sequencing row lock through commit. Explain the resulting per-tenant write serialization. A standalone database sequence must not be described as a commit-order guarantee.

Required endpoints:

~~~text
POST /api/v1/accounts
POST /api/v1/journals
POST /api/v1/journals/{id}/reversal
GET  /api/v1/accounts/{id}/balance?as_of_sequence=...
GET  /api/v1/journals/{id}
POST /api/v1/statements/import
POST /api/v1/reconciliation/runs
GET  /api/v1/reconciliation/runs/{id}
POST /api/v1/reconciliation/proposals/{id}/decision
~~~

Authorization derives the tenant from verified membership, never an unchecked body field. Include tenant-aware pagination, useful validation errors, and audit records for proposal decisions.

### 10.4 Reconciliation algorithm

Normalize statement rows and journal-side candidate entries. Construct a bounded bipartite graph. Score candidates using documented, configurable features; exact unique references may match automatically. Implement a Python minimum-cost matching solver for small connected components.

Scope each run to one tenant and simulated bank account. Right-hand candidates are immutable postings on that account, identified by posting ID. Approved matches enforce database uniqueness for both statement-row and posting identity across all active runs. Approval is transactional and rejects stale or consumed proposals. Test concurrent approvals from separate runs for the same row or posting. Undo, if supported, is an explicit audited revocation event.

Initially cap a component at 32 statement rows and 256 candidate edges. Include an unmatched option. Verify tiny components by exhaustive enumeration. Detect multiple equally optimal solutions; deterministic tie-breaking does not make an ambiguous match certain.

Reimported statements are idempotent by stable source identity and row identity. Fuzzy and ambiguous results remain proposals until explicitly approved. No financial record may be silently “fixed” by a reconciliation heuristic.

### 10.5 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| ME-01 | Reject unbalanced/mixed-currency/invalid-precision journals and preserve allocation totals for positive and negative amounts |
| ME-02 | Submit the same request concurrently and after a lost response; produce one journal and reject mismatched idempotency payloads |
| ME-03 | Execute opposite-direction concurrent transfers on real PostgreSQL; preserve balances and retry whole failed transactions correctly |
| ME-04 | Interrupt posting and prove no partial journal/projection/idempotency result; direct prohibited database edits also fail |
| ME-05 | Rebuild balances independently after randomized postings/reversals and match current and as-of-sequence queries |
| ME-06 | Reject cross-tenant account references and prevent tenant leakage through all reads, exports, and reconciliation operations |
| ME-07 | Solve hand-checkable graphs, detect ambiguous optima, handle repeated imports, bound large components, and reject conflicting concurrent approvals across runs |
| ME-08 | Demonstrate migrations from a previous fixture schema, snapshot backup/restore, and an operator audit exposing an intentionally inconsistent derived projection |

### 10.6 Demo, benchmark, and scope

ci uses 1,000 journals, 200 accounts, 500 statement rows, and eight concurrent clients. Standard uses 250,000 journals, approximately one million postings, 10,000 accounts across 100 tenants, and 100,000 statement rows with controlled duplicates and ambiguities.

Report posting latency/throughput, lock waits, retry rate, replay time, statement normalization rate, graph sizes, and solver time. Separate same-tenant contention from many-tenant throughput. Small labeled reconciliation cases establish correctness; large synthetic cases establish scale behavior.

**Optional extensions:** partial reversals, CSV export, read-only audit dashboard.  
**Excluded:** real banking connectors, moving money, tax calculations, regulatory certification, and distributed ledger consensus.

---

## 11. A05 — Quarry: incremental lakehouse and data-quality engine

**Owner:** A05  
**Path:** projects/05-quarry/  
**Package:** pp_quarry  
**Primary interface:** CLI, Python API, and reproducible analytical reports  
**Product objective:** Turn changing source files into correct, versioned analytical datasets with explainable incremental work.

### 11.1 What to build

Build a local pipeline engine that ingests immutable CSV/NDJSON event files, validates explicit contracts, plans a transformation DAG, applies upserts/deletions/corrections, publishes immutable Parquet snapshots, and records column/dataset lineage.

The default application transforms synthetic device and maintenance data into curated device facts, daily statistics, and data-quality reports. Later files include corrected measurements, deletes, repeated deliveries, and schema changes.

Use one local writer and concurrent snapshot readers. Do not attempt full Iceberg/Delta compatibility or cloud-object-store coordination.

### 11.2 Stack and module ownership

Use PyArrow for explicit schemas and bounded record batches, DuckDB for analytical execution and Parquet queries, SQLite for the transactional catalog, and standard Python for planning and publication. Arrow and DuckDB supply data-processing primitives; the project's original core is incrementality, version semantics, contracts, lineage, and recovery. [S18]

Use Polars only for a specific measured benefit and explain that choice. Do not maintain duplicate Arrow, DuckDB, and Polars execution paths merely to list all three.

| Module under src/pp_quarry/ | Required implementation |
| --- | --- |
| sources/ | Bounded input readers, immutable content identity, source checkpoints |
| model/events.py | Key/version/operation contract and canonical identity |
| planning/dag.py | Dependencies, cycle detection, fingerprints, affected-node plan |
| planning/partitions.py | Stable key buckets and affected-bucket calculation |
| contracts/ | Schema compatibility, declarative row/dataset rules, diagnostic samples |
| execution/ | Batch processing, reductions, keyed upsert/delete merge |
| storage/ | SQLite catalog, manifests, checksummed Parquet, snapshot handles |
| lineage.py, recovery.py | Source/column lineage, orphan reconciliation, restart behavior |
| query.py, cli.py | Pinned-snapshot queries, explain, build, validate, inspect |

Begin with model/events.py, planning/dag.py, and a tiny independent full-rebuild oracle. Define the version/tombstone behavior before performance optimization.

### 11.3 Incremental and publication contracts

Every input event has key, version, operation, and payload. The highest explicit version wins regardless of arrival order. Identical key/version/content is a replay; equal key/version with different content is a conflict. Keep versioned tombstones so old data cannot resurrect after a delete.

Specify source_namespace, canonical key bytes, a nonnegative integer version, upsert/delete operation, and a canonical delete-payload policy. Persist exact content fingerprints for every accepted (source_namespace, key, version), including obsolete versions. Check this registry before latest-state reduction and commit new identities with the manifest/checkpoint. Test a historical equal-version conflict after newer updates, deletion, compaction, and restart; a Bloom filter alone cannot make this authoritative decision.

Track processed file hashes and offsets independently from event versions. A maximum event timestamp or maximum observed version is not a complete ingestion cursor for late-arriving files.

Use stable hash(key) buckets. Corrected records and tombstones reach the same bucket. Date partitioning is an optional extension because a correction that changes the date must remove the old partition entry as well as write the new one.

Define the stored bucket hash algorithm over canonical key bytes, its salt if any, and the bucket count in the dataset format. Never use Python's randomized hash() for persistent buckets. Changing bucket count requires a migration.

Support a small declarative DAG with three real transformations. Node identity includes transform code/config digest, input snapshot IDs, schema, and relevant contract versions. Detect cycles before execution. Reuse a node only if all semantic inputs match.

The baseline transforms are row normalization/projection, versioned device-fact materialization, and daily aggregation. Corrections/deletes invalidate groups derived from both the previous record and its replacement; test moving a record between days and deleting the last record in a group. Fingerprint partition-local inputs at partition granularity. A node that consumes the whole dataset must declare a global dependency and may recompute globally. Do not promise partition reuse while invalidating every node from an unrelated global snapshot ID.

Publish in this order:

1. Produce uniquely named immutable Parquet files in the owned dataset directory.
2. Validate row/schema/size/checksum expectations and complete required persistence operations.
3. Commit the new manifest, lineage, and ingestion checkpoint in one SQLite transaction.
4. Make the committed snapshot available to readers.
5. Reconcile orphan files separately after interrupted unpublished runs.

Readers use only files listed in a pinned manifest. Never query a directory glob that can include uncommitted files. The guarantee is atomic manifest visibility under the documented filesystem assumptions, not atomicity of unrelated file writes.

Retain snapshots by default. Garbage collection must be an explicit command, respect retention and active readers, and operate only in the owned dataset directory.

Automatic schema evolution is limited to additive nullable columns. Renames, narrowing, key changes, and incompatible types need explicit migration instructions. Required strict validation rejects the batch without advancing its checkpoint. A quarantine mode is optional and needs a separate partial-acceptance contract.

Required CLI commands include ingest, plan, build, validate, query, snapshots, lineage, recover, and explain.

### 11.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| QU-01 | Match incremental results to an independent complete rebuild after original, repeated, and out-of-order files |
| QU-02 | Preserve corrections and deletes, reject equal-version conflicts, and prevent older upserts from resurrecting tombstoned rows |
| QU-03 | Rebuild only affected buckets/downstream nodes and prove unchanged node reuse from recorded fingerprints |
| QU-04 | Detect DAG cycles, invalid transforms/configuration, and malformed source records before publishing an invalid snapshot |
| QU-05 | Accept supported nullable additions; reject incompatible schema changes with a useful migration diagnostic |
| QU-06 | Crash after file creation, before catalog commit, and after commit; restore consistent visible data and checkpoints |
| QU-07 | Query an older pinned snapshot during a new publication and preserve its historical rows; GC respects retained/active snapshots |
| QU-08 | Process bounded batches, enforce memory configuration, and show source-to-output lineage for a deliberately wrong source record |

### 11.5 Demo, benchmark, and scope

ci uses 20,000 events across eight buckets with 10% corrections and 2% deletes. Standard uses five million events across 128 buckets followed by separate late-update, delete, and schema-evolution batches.

Show the original build, a one-bucket correction plan, a failed validation, a recovered interrupted publication, and a query against an old snapshot. Output a plan explanation and a compact lineage/quality report.

Measure rows/second, peak memory, bytes read/written, rewritten buckets, reused nodes, query time, recovery time, and incremental/full rebuild ratios. Report batch sizes and DuckDB memory/thread settings. Do not materialize the complete dataset into Python lists.

**Optional extensions:** incremental joins, quarantine mode, a verified Polars adapter, date partition migrations.  
**Excluded:** a complete distributed lakehouse, cloud atomicity claims, Kafka ingestion, and reimplementation of a columnar query engine.

---

## 12. A06 — PyTrace: static analysis and safe refactoring toolkit

**Owner:** A06  
**Path:** projects/06-pytrace/  
**Package:** pp_pytrace  
**Primary interface:** CLI, Python API, JSON, SARIF, and reviewable patches  
**Product objective:** Explain meaningful Python code risks and apply narrowly justified transformations without executing the target program.

### 12.1 What to build

Build a Python analyzer with source discovery, name/alias resolution, function control-flow graphs, flow-sensitive intraprocedural dataflow, a monotone fixed-point engine, incremental invalidation, three substantial rules, and two conservative codemods.

The rules are:

1. Configured untrusted input flowing to a subprocess call with shell=True.
2. String-built SQL flowing to configured execution sinks, distinguished from supported parameterized forms.
3. Configured blocking synchronous calls inside async functions, with import aliases and local shadowing respected.

The analyzer must explain the flow and its uncertainty. Its job is not to claim that every dynamic Python program is statically understood.

### 12.2 Stack and module ownership

Use ast for semantic structure and LibCST for formatting-preserving edits and qualified-name/scope metadata. Match supported grammar to the actual interpreter/parser versions; AST shapes can change with Python releases. [S19]

| Module under src/pp_pytrace/ | Required implementation |
| --- | --- |
| frontend/ | Discovery, exclude rules, encodings, parse limits, syntax diagnostics |
| semantics/ | Symbols, aliases, shadowing, dependency graph, unknown targets |
| cfg/ | Basic blocks, branches, loops, returns, documented exception edges |
| analysis/ | Finite abstract lattice, monotone joins, worklist, configured call summaries |
| rules/ | Three original analyses and rule-specific evidence |
| reporting/ | Source-to-sink paths, text/JSON output, SARIF 2.1.0 |
| codemods/ | Preconditions, LibCST transforms, edit conflict checks, patch generation |
| cache.py | Content/parser/rule/config/dependency fingerprints and invalidation |
| cli.py | Analyze, explain, diff, apply, cache inspect, demo |

Start with cfg/blocks.py, analysis/lattice.py, and one hand-drawn control-flow fixture. Add the rules to a common analysis engine; do not implement three unrelated text searches.

### 12.3 Analysis and transformation contracts

The baseline is intraprocedural and flow-sensitive. Explicitly model assignment, reassignment, concatenation, branch joins, loops, and configured sources/sinks/sanitizers. Bound the lattice so the worklist terminates. Do not reuse evidence strings as the semantic abstract state.

Unknown calls, dynamic imports, reflection, exec, unresolved aliases, and unsupported exception behavior must produce uncertainty or a documented analysis boundary. Do not silently treat unknown data as safe. Sanitizers are context-specific; shell sanitization must not imply SQL sanitization.

Respect shadowing, for example a local variable named subprocess or a redefined sleep. State how comprehensions, closures, and nested functions are handled. A complete symbol model and a bounded dataflow contract are more credible than undocumented guesses.

Each diagnostic includes rule_id, severity, confidence/coverage status, source location, relevant sink location, evidence path, and a useful explanation. Convert AST byte offsets and output column conventions deliberately, especially for Unicode source. Validate SARIF against the official 2.1.0 schema. [S20]

Implement these two required conservative codemod categories with concrete fixtures:

- **Redundant literal constructor:** remove an unshadowed built-in str() call around a string literal, subject to comment/formatting constraints and the documented lexical name-resolution model.
- **Configured API migration:** rename a keyword-only parameter at calls to a known imported API whose old/new equivalence is defined by a trusted fixture library in this repository.

For the literal transform, require exactly one positional str literal, no keywords/unpacking, no bytes, and no f-string. Abstain if the replacement would create a docstring in the first statement of a module/class/function/async function; parentheses do not avoid that change. Preserve comments or abstain. State the equivalence assumption of no runtime rebinding or reflective/tracing observation of the removed built-in call.

The API migration manifest identifies the canonical callable, supported fixture API version/hash, old keyword, new keyword, and preconditions. Require one explicit old keyword, no explicit new keyword, no **kwargs, and an unambiguous binding. Rename without moving or duplicating the value expression. Verify equivalent behavior/error cases only on trusted fixture API versions, never by executing the analyzed target.

Do not auto-fix tainted shell commands, SQL, or blocking async behavior. Such rewrites can change semantics. Abstain on dynamic aliases, **kwargs, conflicting bindings, overlapping edits, unsupported syntax, or uncertain metadata. A no-op/abstention is the correct result when preconditions fail.

Produce a unified patch by default. Explicit apply checks original file hashes, preserves line endings/comments, writes only selected files, and compiles the result without running target code. Applying the same transform twice produces no further change. Multi-file edits require a recoverable plan; do not claim a collection of independent replacements is one atomic filesystem operation.

Run target parsing in bounded subprocesses with file/count/timeout limits and supported memory limits. Do not import the target, execute its build hooks, load its plugins, or evaluate its configuration as Python.

### 12.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| PY-01 | Match labeled positive/negative cases for all three rules, including aliasing, reassignment, shadowing, and path joins |
| PY-02 | Show fixed-point convergence on loops and conservative handling of unknown calls and unsupported constructs |
| PY-03 | Emit correct source locations/evidence for Unicode, multiline expressions, syntax errors, and suppression directives |
| PY-04 | Validate SARIF structure and stable diagnostic identifiers; repeated identical runs produce equivalent findings |
| PY-05 | After local and dependency edits, incremental analysis equals a clean run and invalidates the necessary inputs |
| PY-06 | Apply both codemods to eligible trusted fixtures, preserve behavior/comments, and verify idempotence |
| PY-07 | Refuse uncertain rewrites, stale content hashes, overlapping edits, and malformed/path-escaping inputs |
| PY-08 | Enforce parser resource limits and prove target imports/executable configuration are never executed during analysis |

### 12.5 Demo, benchmark, and scope

ci uses at least 50 carefully labeled fixture files and approximately 5,000 lines with genuine positive and negative cases. Standard analyzes a pinned, license-compatible 250,000-line corpus plus a generated dependency graph for repeatable invalidation tests.

The demonstration analyzes an intentionally flawed synthetic service, explains three findings, previews two safe edits, applies them to trusted test fixtures, and reanalyzes. Never modify a third-party repository merely to demonstrate the tool.

Measure cold/incremental runtime, peak memory, files invalidated, parse failures, and rule precision/recall only on the hand-labeled corpus. Large unlabeled source establishes throughput, not diagnostic accuracy.

**Optional extensions:** a small LSP adapter, interprocedural summaries for a bounded subset, IDE-friendly output.  
**Excluded:** complete Python soundness, a full type checker, automatic security certification, arbitrary plugins, and executing untrusted target tests.

---

## 13. A07 — Atlas: permission-aware document search engine

**Owner:** A07  
**Path:** projects/07-atlas/  
**Package:** pp_atlas  
**Primary interface:** CLI, Python retrieval API, FastAPI, and a focused search view  
**Product objective:** Retrieve relevant documents with explainable ranking while enforcing visibility before results are selected.

### 13.1 What to build

Implement an offline lexical search engine for text and Markdown with Unicode normalization, positional inverted indexes, document revisions, immutable index generations, a bounded query language, BM25 ranking, phrase search, snippets, relevance evaluation, and tenant/principal permissions.

Build the lexical implementation yourself. An optional local reranker can follow; neither a hosted search service nor a paid LLM is a required dependency.

The default corpus is a small original technical knowledge base with runbooks, design notes, incident reports, and intentionally restricted documents. The demo changes a permission, updates a document, merges index segments, and proves the visible results remain correct.

### 13.2 Stack and module ownership

Use standard Python data structures, regex/unicodedata, heapq, SQLite catalog metadata, typed records, FastAPI, Pydantic, pytest, and Hypothesis. Use memory-mapped or compressed segments only after measuring the baseline.

| Module under src/pp_atlas/ | Required implementation |
| --- | --- |
| ingest/ | Bounded readers, normalization, stable document/revision identity |
| index/ | Positional postings, immutable segments, external merge, generation metadata |
| ranking/ | BM25, deterministic top-k heap, score explanations, optional rerank adapter |
| auth/ | Verified tenant/principal context, group membership, ACL revisions, visible sets |
| query.py | Bounded parser, terms/phrases/filters, candidate planning |
| snippets.py | Source-offset mapping, escaped excerpts, visibility-safe highlighting |
| catalog.py, snapshots.py | Current revisions, generation publication, reader handles |
| cache.py | Permission/index-aware result caching |
| evaluation.py | Judged relevance evaluation and per-query error analysis |
| api/, cli.py | Search, ingest, update, delete, grant/revoke, inspect, evaluate |

Start with ranking/bm25.py, index/postings.py, and a six-document hand-calculated test corpus.

### 13.3 Ranking and authorization contracts

Choose and document this BM25 variant, then verify it by hand on a tiny corpus:

~~~text
IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(d, q) = sum over unique query terms t of:
  IDF(t) * tf(t,d) * (k1 + 1)
  / (tf(t,d) + k1 * (1 - b + b * length(d) / average_length))
~~~

Start with k1 = 1.2 and b = 0.75 as chosen configuration defaults, not universally optimal values. Define empty-corpus/empty-document behavior and deterministic tie-breaking by stable document ID. The BM25 family and length-normalization concepts are described in the Stanford information-retrieval text. [S21]

Physically separate tenant index/catalog namespaces. Within a tenant, derive:

~~~text
visible_set = authorized_documents
              intersect current_document_revisions
              intersect explicit_query_filters
~~~

Intersect postings with that set before scoring, top-k selection, phrase evaluation, snippets, counts, or facets. For the required reference implementation, N, df, and average_length are computed over the same visible set. Hidden documents must not affect a user's visible score through global statistics.

Cache keys include verified tenant identity, permission-set digest, ACL revision, index generation, normalized query, filters, and ranking parameters. Permission checks apply to document routes and exports as well as the search endpoint.

Define authorization as a snapshot at request start. Every request beginning after a revocation commits observes it; document any already-running request semantics. On index updates, use the current revision/deletion catalog so an older segment cannot re-expose deleted or superseded content.

Publish index generations atomically through metadata after referenced segments are complete. Readers pin a generation. Segment merging must preserve scores, phrase positions, and visible revisions. Detect segment corruption and fail clearly.

Capture one coherent tenant catalog snapshot at request start: active index generation, active revisions/deletions, ACL revision/memberships, and tokenizer/configuration version. Compute visibility/statistics from revisions present in that snapshot and generation. Publish a completed generation and its corresponding active revision metadata in one catalog transaction. ACL updates remain independently publishable, and subsequent requests observe their committed revision.

If adding dense reranking, give it only authorized lexical candidates and explicitly provided local model files with provenance. The base installation and acceptance tests must work without downloading a model.

### 13.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| AT-01 | Match hand-calculated BM25 scores/ranks, query-term policy, deterministic ties, and empty cases |
| AT-02 | Verify Unicode normalization, phrase positions, repeated terms, bounded queries, and correctly escaped snippets |
| AT-03 | Preserve results through flush/segment merge and concurrent generation publication |
| AT-04 | Update/delete documents and prove obsolete revisions never reappear through search or direct fetch |
| AT-05 | Test cross-tenant and within-tenant ACL isolation across snippets, counts, facets, exports, and cache entries |
| AT-06 | Modify only hidden documents and preserve visible scores/counts/snippets under the defined visible-statistics contract |
| AT-07 | Revoke access and make the next query observe it; reject corrupted segments and malformed/unbounded inputs |
| AT-08 | Evaluate independently judged queries, report per-query ranking failures, and improve one documented weakness without tuning on held-out judgments |

### 13.5 Demo, benchmark, and scope

ci uses 200 original documents and 30 smoke queries. Maintain a separate quality corpus of at least 250 original or appropriately licensed documents and 60 independently written graded queries. Split development and held-out evaluation queries before tuning.

Standard uses 100,000 generated documents averaging 400 tokens and 2,000 queries with documented term/selectivity distributions. Measure indexing time, disk size, peak memory, cold/warm query latency, and authorization cost.

Report nDCG@10, MRR, and Recall@k only where judgments support them. Define the relevance labels, unjudged-document policy, and whether recall is over a complete or pooled relevant set. Generated scale data does not demonstrate relevance quality.

**Optional extensions:** local dense reranking, bounded PDF-text ingestion, a small evaluation comparison view.  
**Excluded:** a chatbot, external crawling, OCR, foundation-model training, or claims to eliminate every timing side channel.

---

## 14. A08 — Proving Ground: reproducible ML experiment and promotion platform

**Owner:** A08  
**Path:** projects/08-proving-ground/  
**Package:** pp_proving_ground  
**Primary interface:** CLI, model registry API, prediction endpoint, and experiment reports  
**Product objective:** Make an ML result reproducible, evaluate it correctly, and promote/roll back a model through explicit verified state.

### 14.1 What to build

Build a complete lifecycle for one tabular binary-classification problem: predict a synthetic equipment fault within a documented future horizon. Generate the offline dataset, freeze train/validation/test membership, train a logistic baseline and a tree-based model, evaluate them, store content-addressed artifacts, enforce promotion rules, serve predictions, and diagnose data drift.

The original Python engineering core is dataset/run identity, split-policy enforcement, leakage checks, evaluation/promotion decisions, artifact integrity, and serving-version consistency. scikit-learn supplies estimators. Do not install MLflow and present its capabilities as this project's implementation.

### 14.2 Stack and module ownership

Use NumPy, scikit-learn, PyArrow, SQLite, FastAPI, Pydantic, Typer, pytest, and Hypothesis. Use a constrained supported model-serialization route such as skops with explicit type review. No GPU is required.

| Module under src/pp_proving_ground/ | Required implementation |
| --- | --- |
| data_contracts/ | Feature types, label horizon, availability-time metadata, dataset provenance |
| splits/ | Immutable split manifests, temporal purge/embargo, optional entity holdout |
| experiments/ | Canonical specifications, run identity, attempts, seed/environment capture |
| training/ | Train-only fitted preprocessing and estimator execution |
| evaluation/ | Baselines, discrimination/calibration, slice metrics, uncertainty, gate decisions |
| artifacts/ | Content-addressed store, staged writes, checksums, manifests |
| registry/ | Model versions, promotion audit, generation comparisons, rollback |
| serving/ | Input validation, complete pipeline loading, prediction/version responses |
| monitoring/ | Schema failures, descriptive distribution-shift reports |
| cli/, reports/ | Generate, train, evaluate, promote, predict, rollback, model card |

Principal records are DatasetVersion, SplitManifest, ExperimentSpec, RunRecord, EvaluationReport, ArtifactManifest, ModelVersion, PromotionDecision, and DeploymentGeneration.

Begin with data_contracts/schema.py, splits/manifest.py, experiments/identity.py, and tests that intentionally break temporal/split rules.

### 14.3 Dataset, evaluation, and promotion contracts

Every row has a stable row ID, asset ID, observation time, feature availability times, and label availability time. The default temporal split excludes training observations whose label horizon crosses the validation boundary; define the purge/embargo interval explicitly.

Support a distinct entity-holdout policy that enforces disjoint asset IDs. Do not claim that a temporal split automatically prevents entity overlap or that an entity split automatically models future forecasting. Record the intended question for each evaluation.

All learned preprocessing fits only on the permitted training data. Freeze split membership before training. Keep the final test set out of hyperparameter selection and repeated promotion tuning. scikit-learn documents leakage through preprocessing and the role of pipelines in preventing inconsistent training/evaluation transformations. [S22]

Required leakage checks detect overlapping row membership, policy-violating group overlap, unavailable features, future label-derived declared features, and incompatible split manifests. State that these checks verify declared data contracts; they do not automatically discover every hidden causal leakage in arbitrary data.

Use at least a majority/prior baseline, logistic model, and one tree model. Report class balance, PR-AUC, ROC-AUC where defined, Brier score, calibration bins, and relevant slice counts. Avoid a single accuracy number. Use a bootstrap unit appropriate to correlated asset/time observations, and document uncertainty rather than treating tiny slices as reliable.

A run's semantic identity includes data, split, code, preprocessing, hyperparameters, seed, and lock digests. Timestamps are attempt metadata. Retries can share an experiment identity while recording separate attempts.

Artifact publication uses immutable content and an atomic manifest/registry transition. Verify all hashes before loading. Do not accept arbitrary uploaded pickle/joblib files. Integrity hashes do not make executable serialization safe, and library versions affect persistence compatibility. [S23]

Promotion is conditional on the current registry generation and evaluated validation gates. Two competing promotions cannot silently overwrite one another. Record requested deployment generation separately from the model actually loaded by a serving process. Every prediction returns the actual loaded model/version; readiness must reveal a failed or pending load.

A promotion decision binds the candidate artifact, dataset/split digests, evaluation report, gate-policy version, and expected registry generation. Missing, nonfinite, undefined, or insufficient-sample required metrics make the candidate ineligible. A passing report for a different artifact/split cannot authorize this candidate. Test a missing metric and a one-class validation case where a required metric is undefined.

Offline batch inference and online inference use the identical fitted pipeline. Rollback creates an auditable generation transition; it does not delete model history. Serve the previously loaded model or report unavailable if a new candidate cannot load; never label old predictions with the new candidate's ID.

Each request captures one immutable serving snapshot containing the pipeline, artifact digest, model version, and applied deployment generation. Inference and response metadata use that same snapshot. Load candidates before an atomic snapshot swap; a completed load checks that its requested generation remains applicable, so an older slow load cannot replace a newer deployment. Expose the applied generation separately from model version, since rollback may reference an older model in a newer generation.

Drift reports describe distribution differences and schema failures. They do not by themselves prove accuracy degradation without labels.

### 14.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| PG-01 | Generate, freeze splits, train baselines/candidate, evaluate, and reproduce predictions within a declared numerical tolerance |
| PG-02 | Reject deliberately overlapping splits, policy-violating entities, unavailable features, and declared future-derived leakage |
| PG-03 | Prove preprocessing learns only from training rows and that held-out test judgments do not choose promotion thresholds |
| PG-04 | Reject a failing candidate, promote a passing candidate, and audit the metrics/rules responsible |
| PG-05 | Race promotions and out-of-order load completions, enforce generation comparison, and prevent an obsolete load from replacing a newer deployment |
| PG-06 | Match offline and HTTP predictions; reject corrupted, unsupported, or untrusted model artifacts |
| PG-07 | Roll back, fail candidate loading, and force a prediction across a model swap; its metadata must match the exact pipeline and applied generation used |
| PG-08 | Inject feature drift and schema changes, produce a descriptive monitoring report, and recover cleanly from an interrupted run/artifact write |

### 14.5 Demo, benchmark, and scope

ci uses 5,000 generated rows across multiple assets and a small fixed estimator configuration. Standard uses 250,000 rows and approximately 40 features with time correlation, class imbalance, missingness, and a controlled shift.

Report training/inference times, artifact sizes, memory, validation metrics, calibration, slice sample sizes, and registry/serving transition latency. Compare five repeated inference runs with explicit thread configuration. Do not claim byte-identical model serialization across platforms.

The demo walks from dataset lineage to a rejected model, an accepted model, live predictions, a corruption refusal, rollback, and a model card. A tiny local report should show the evidence that caused each decision.

**Optional extensions:** MLflow export, local experiment comparison UI, one additional estimator family.  
**Excluded:** distributed/GPU training, AutoML, arbitrary model support, Kubernetes, and guaranteed predictive performance on real equipment.

---

## 15. A09 — Routecraft: routing and scheduling optimization engine

**Owner:** A09  
**Path:** projects/09-routecraft/  
**Package:** pp_routecraft  
**Primary interface:** CLI, Python solver API, JSON plan, and visual route/timeline report  
**Product objective:** Find and explain feasible vehicle schedules under explicit constraints, with honest solution-quality reporting.

### 15.1 What to build

Solve a capacitated vehicle-routing problem with a single depot, asymmetric static travel-time matrices, service durations, customer time windows, vehicle shifts, and rolling replanning.

Implement original feasible insertion, regret insertion, relocation/swap improvements, and adaptive large-neighborhood search in Python. Maintain an independent verifier and a deliberately small exact reference solver. OR-Tools may provide an optional comparison adapter; the default solver must run the authored algorithm.

The default application plans a fictional island delivery fleet using synthetic locations and travel matrices. Generated coordinates are visual aids, not a claim to use actual roads or live traffic.

### 15.2 Stack and module ownership

Use dataclasses/Pydantic, NumPy where useful, heapq, a controlled RNG, Typer, Matplotlib, pytest, and Hypothesis. An HTML report may add a small interactive timeline, but the solver and verifier are the main work.

| Module under src/pp_routecraft/ | Required implementation |
| --- | --- |
| domain/ | Stops, vehicles, depot, matrices, units, windows, routing instances |
| validation/ | Input checks and independent route/schedule/objective verification |
| construction/ | Feasible greedy and regret insertion |
| neighborhoods/ | Destroy/repair, relocation, swap, route-local moves |
| search/ | Operator weighting, acceptance policy, budgets, best incumbent |
| replanning/ | Frozen prefixes, current vehicle state, valid suffix planning |
| reference/ | Exhaustive search for tiny instances and optional comparison adapter |
| reporting/ | Route map, timeline, objective breakdown, rejected-constraint diagnostics |
| cli.py | Generate, solve, verify, replan, compare, demo |

Principal records include RoutingInstance, Stop, Vehicle, VehicleState, Route, VisitSchedule, Plan, SearchBudget, and SolveResult.

Begin with domain/instance.py, validation/verifier.py, and tiny hand-checkable instances. Write the verifier before optimizing move deltas.

### 15.3 Constraint and search contracts

Use integer units for time, demand, capacity, and costs. Define whether time windows constrain arrival or service start; use service start for the required baseline. Include waiting time and return-to-depot shift feasibility.

Each complete plan visits every mandatory stop exactly once and obeys capacity, time windows, shifts, and depot requirements. The independent verifier recomputes all schedules and costs from input data. It must not trust optimizer caches.

Use a lexicographic objective: first minimize vehicles used among feasible complete plans, then total travel time. Document any later cost model as a versioned option. Do not hide violated hard constraints inside a large penalty and call the result feasible.

For asymmetric matrices, route reversal changes internal arc directions. Either recompute affected routes or implement a correct directed delta; a symmetric 2-opt formula is not sufficient.

Provide both an iteration-budget mode for reproducible tests and a wall-clock-budget mode for practical use. The same seed plus a wall-clock deadline need not execute the same number of iterations. Report stopping reason and actual iterations.

Solver states are:

~~~text
OPTIMAL
FEASIBLE
PROVEN_INFEASIBLE
NO_FEASIBLE_PLAN_FOUND
INVALID_INPUT
~~~

A heuristic timeout is not proof of infeasibility. An optimality gap requires a valid bound; otherwise display “unknown.” Distinguishing a feasible answer from an optimal one and from an unknown search outcome is also explicit in OR-Tools' status semantics. [S24]

For replanning, freeze executed route prefixes and start from the vehicle's actual current position, time, and remaining load. The baseline keeps already loaded deliveries on their assigned vehicle. New deliveries may enter an unstarted vehicle's plan; reloading and transfers are optional extensions. Do not let an optimization move cargo or completed stops retroactively.

VehicleState distinguishes capacity, onboard quantity, and IDs/quantities of remaining loaded jobs. Deliveries reduce onboard quantity; spare capacity does not create cargo for a new job. Started vehicles cannot accept new unloaded jobs, and loaded jobs cannot switch vehicles. Required replanning occurs at service-completion/departure boundaries at named matrix nodes. Reject unsupported mid-edge/in-service snapshots. A new customer supplies an expanded matrix whose existing-node costs remain unchanged unless a new matrix version is explicitly declared.

The tiny reference solver must exhaustively enumerate sufficiently small instances, initially up to six customers and two vehicles, to verify objective values and genuine infeasibility. Do not reuse the production neighborhood code as its oracle.

### 15.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| RC-01 | Match exhaustive tiny-instance objective values and proven infeasibility on hand-checkable fixtures |
| RC-02 | Reject duplicate/missing stops, capacity overflow, window/shift violations, and inconsistent cached objective values |
| RC-03 | Test asymmetric travel matrices and demonstrate correct move-cost/schedule recalculation |
| RC-04 | Preserve a valid best incumbent through rejected moves, cancellation, and wall-clock timeout |
| RC-05 | Reproduce iteration-budget results with the same input/seed and report actual search effort |
| RC-06 | Compare authored heuristics to their construction baseline under stated equal budgets and publish failures as well as gains |
| RC-07 | Replan around a new request; reject changed executed stops, transferred onboard jobs, new unloaded jobs on started vehicles, inconsistent cargo manifests, and unsupported mid-edge states |
| RC-08 | Produce independently verified JSON plus route/timeline reports, and distinguish no solution found from proven infeasibility |

### 15.5 Demo, benchmark, and scope

ci includes exact tiny cases plus a 25-stop heuristic scenario. Standard includes 25-, 100-, and 500-stop tiers, several seeded instances per tier, tight/loose time windows, asymmetric matrices, and a replanning scenario.

Measure feasible-solution rate, objective against baseline, time/iterations to first feasible plan, improvement trajectory, verifier cost, memory, and actual search budget. Include cases where no improvement is found. A tiny exact optimum is evidence only for that instance.

The demonstration shows construction, improvement, a route intentionally rejected by the verifier, a new delivery request, and valid replanning with a visual timeline.

**Optional extensions:** OR-Tools comparison, reload visits, pickup-and-delivery constraints, a small what-if viewer.  
**Excluded:** live road routing, multi-depot operations, global-optimum guarantees for large instances, and fabricated infeasibility certificates.

---

## 16. A10 — Resonance: guitar audio analysis and transcription workbench

**Owner:** A10  
**Path:** projects/10-resonance/  
**Package:** pp_resonance  
**Primary interface:** CLI, Python analysis API, audio/MIDI outputs, and an annotated report  
**Product objective:** Turn a monophonic guitar phrase into interpretable pitch, onset, intonation, and timing evidence.

### 16.1 What to build

Build an offline analysis workbench for monophonic guitar phrases and practice recordings. Estimate a pitch trajectory, distinguish voiced/unvoiced frames, detect onsets, group note events, align them to a small reference-score format, and report intonation/timing deviations.

Implement the framing, pitch-estimation, onset, temporal decoding, and alignment logic in Python/NumPy. Use SciPy for numerical primitives and independent comparisons. An optional librosa comparison may help evaluation but must not provide the entire required analysis.

This project should have a musician-facing result: a playable waveform/spectrogram report with note boundaries, pitch in cents, aligned reference notes, confidence indicators, and a downloadable monophonic MIDI transcription. It provides a distinctive portfolio demonstration grounded in an actual musical use case.

### 16.2 Stack and module ownership

Use NumPy, SciPy, SoundFile, Matplotlib, a small MIDI library such as mido, pytest, and Hypothesis. No cloud transcription, pretrained weights, microphone permission, or GPU is required.

| Module under src/pp_resonance/ | Required implementation |
| --- | --- |
| audio_io/ | File/PCM conversion, sample-rate limits, channel and clipping policy |
| streaming/ | Bounded buffers, integer sample positions, overlap, flush behavior |
| spectral/ | Windowing, STFT, spectral flux, reference comparisons |
| pitch/ | YIN-style difference/normalization/interpolation, voiced confidence |
| onsets/ | Adaptive thresholding, peak selection, onset confidence |
| notes/ | Confidence-aware note segmentation and temporal smoothing |
| alignment/ | Monotone dynamic-programming alignment with extra/missing notes |
| metrics/ | Pitch error, onset/timing error, note-event quality, confidence summaries |
| synthesis/ | Annotated tones, guitar-like plucks, harmonics, vibrato, bends, noise |
| reports/, midi/ | Playable report, JSON events, explicit MIDI timing/rounding |
| cli.py | Synthesize, analyze, align, compare, export, demo |

Principal records are AudioSpec, FrameConfig, PitchFrame, OnsetEvent, NoteEvent, ReferenceNote, AlignedNote, AnalysisConfig, and AnalysisReport.

Begin with streaming/framing.py, synthesis/tones.py, pitch/difference.py, and tests whose pitch/time ground truth comes from the signal generator parameters.

### 16.3 Numerical and musical contracts

Use integer sample positions as the timing authority. Derive seconds from sample rate when presenting results. Specify frame size, hop size, padding, center/start timestamp convention, and algorithmic lookahead.

Implement a YIN-style pitch estimator with an explicit lag range, cumulative normalization, threshold policy, interpolation, and voiced/unvoiced decision. Cite the original method and document deliberate changes. [S26]

Support the baseline guitar range E2–E6 on 44.1 kHz and 48 kHz mono/stereo PCM inputs. Make the stereo-to-mono policy explicit and test phase-cancellation cases. Handle unsupported rates with a documented rejection or an explicit resampling operation; do not silently reinterpret sample positions.

Silence produces unvoiced frames. Extremely short, clipped, noisy, polyphonic, or low-confidence passages receive useful diagnostics. A pitch estimate with low confidence must not become a definitive musical criticism.

Pitch in cents relative to a reference frequency uses 1200 * log2(estimated/reference). Exclude unvoiced and nonpositive values from that calculation. Declare how bends and vibrato are summarized without flattening them into invented stable notes.

Compare batch and chunked processing using randomized chunk sizes. Chunk boundaries must not reset relevant state, duplicate frames, or shift final timestamps. The required product remains offline; chunk-equivalent processing is a memory/correctness feature, not a claim of hard real-time performance.

Validate STFT/inverse reconstruction for an explicitly supported window/hop/padding configuration against SciPy's reference behavior. Document boundary treatment and numerical tolerances. SciPy's ShortTimeFFT documentation describes its windowed transform and reconstruction behavior. [S25]

Represent the reference score as versioned JSON with note IDs, MIDI pitch, onset/duration units, and an explicit tempo/time mapping. Implement monotone alignment with insertion/deletion/substitution costs, confidence gating, and optional local tempo adjustment. Do not force every detected note to match a reference.

MIDI export needs explicit tempo events, note-off handling, timing quantization, and deterministic note ordering. The required baseline exports monophonic note events; pitch-bend curves are optional and must use an explicit bend range.

### 16.4 Required acceptance gates

| ID | Scenario and evidence required |
| --- | --- |
| RE-01 | On the fixed E2–E6 grid, at least 95% of all predetermined ground-truth-voiced steady-state frames must be classified voiced and estimated within 10 cents |
| RE-02 | Handle silence, short files, clipping, stereo conversion, unsupported rates, and last-buffer flushing without fabricated notes or crashes |
| RE-03 | Match batch and randomized-chunk outputs under documented boundary/tolerance rules |
| RE-04 | Reconstruct the supported STFT fixture within a stated floating-point tolerance and compare key features to an independent reference |
| RE-05 | Recover the intended events of the fixed clean isolated-pluck fixture within predefined onset/note tolerances and invent no events in its silent intervals; report challenge-set errors separately |
| RE-06 | Reproduce the expected match/unmatched mapping for an unambiguous phrase with one inserted and one omitted note; separately analyze bends/vibrato and timing perturbations |
| RE-07 | Export valid MIDI and JSON with consistent note times; round-trip MIDI through an independent parser/checker |
| RE-08 | Produce a playable annotated report, preserve analysis provenance, and process a long recording with bounded chunk buffers |

Define the RE-01 fixture grid, amplitude/noise conditions, eligible steady-state regions, and frame coverage before tuning the estimator. Exclude attacks only by predetermined ground-truth windows, not by removing inconvenient failed estimates. Report voicing recall as well as error among voiced outputs so an estimator cannot pass by abstaining on most frames.

The RE-01 denominator is all predetermined eligible ground-truth frames. Unvoiced, missing, nonfinite, or out-of-tolerance estimates count as failures. Report conditional pitch error separately. Fix RE-05 timing tolerances and permitted miss/false-positive counts before tuning, and require recovery of its clean isolated events. Fix RE-06's expected correspondence beforehand; marking every note unmatched does not pass.

### 16.5 Demo, benchmark, and scope

ci uses approximately one minute of generated clean tones and guitar-like monophonic phrases. Standard uses a ten-minute generated recording with harmonics, noise, bends, vibrato, rests, and annotated timing perturbations.

The default report compares known ground truth to estimated pitch and timing, lets the reviewer hear the original audio, and explains uncertain passages. If appropriate licensed real guitar recordings are available, evaluate them separately and report that synthetic accuracy does not establish real-recording accuracy.

Measure pitch/onset/note metrics, voicing errors, alignment cost and errors, processing time, real-time factor as a measured ratio, peak memory, and thread settings. Do not advertise perfect transcription or judge artistic interpretation from pitch/timing statistics.

**Optional extensions:** microphone input, pitch-bend MIDI, a practice-session viewer, a small locally trained onset model.  
**Excluded:** universal polyphonic transcription, full-band separation, automatic orchestration, subjective musical grading, and hard real-time guarantees.

---

## 17. Coordinator-owned integration demonstrations

The projects remain independent. These three demonstrations test interoperability through public contracts after the individual projects pass their own gates. Keep adapters in integrations/ and execute each product in its own environment.

Add a dispatcher command:

~~~text
python scripts/portfolio.py integration settlement
python scripts/portfolio.py integration stream-lake
python scripts/portfolio.py integration code-search
~~~

### 17.1 IN-01 — Recoverable simulated settlement

**Participants:** Anchor and Meridian  
**Path:** integrations/01-settlement/

An Anchor activity submits a simulated Meridian journal with a stable idempotency key derived from the workflow's business operation. Terminate the activity after the ledger commits but before Anchor records completion. Recover and retry. Verify one logical journal, balanced postings, and a completed workflow history.

A second scenario triggers a supported reversal after the original journal is durably confirmed. Retries retain the original posting key and cannot create another journal. This integration does not claim cancellation-before-first-post support from Meridian; that late-publication race is verified against Anchor's explicitly fenced synthetic provider. Do not claim arbitrary financial services can be rolled back.

**Pass evidence:** original/retried HTTP requests, one journal identity, replayed ledger balances, Anchor history, and final compensation state. Use synthetic local accounts and local services only.

### 17.2 IN-02 — Corrected stream results into historical analytical snapshots

**Participants:** Current and Quarry  
**Path:** integrations/02-stream-lake/

Translate Current window result keys/revisions into Quarry namespaced keys/versions. Deliver a revision twice, deliver a newer revision, then retry the older one. Include a late-event correction that changes an aggregate.

Import those records through Quarry's public ingestion interface. Verify that the latest analytical state matches Current's greatest committed revision and that a previously pinned snapshot retains its historical value.

**Pass evidence:** source/control trace, window-result delivery IDs, bridge mapping, Quarry snapshot manifests, and an independent complete-rebuild comparison. The adapter preserves exact version/conflict semantics; it must not generate a fresh arbitrary version for every retry.

### 17.3 IN-03 — Searchable code-analysis evidence

**Participants:** PyTrace and Atlas  
**Path:** integrations/03-code-search/

Analyze trusted synthetic services with PyTrace, export diagnostics, convert them into a small document corpus, and index it with Atlas. Search by rule, project, and evidence text. Give different synthetic principals different visibility.

Update a source, regenerate diagnostics, and remove obsolete result documents. Verify that search returns current, authorized evidence only and that restricted findings do not affect visible statistics.

**Pass evidence:** original analysis report, document-ID mapping, update/deletion manifest, judged queries, and ACL/cache tests. Search relevance scores are not vulnerability severity or proof that a finding is correct.

### Integration ownership and failure policy

The coordinator owns all adapters, fixture mapping, and contract tests. Project agents fix defects in their own packages through normal handoffs. Do not patch a product's internals from integrations/ or introduce a shared environment that imports all ten projects.

If an integration reveals a real contract mismatch, amend the affected contract once, notify the owners, add a regression case, and reverify affected projects. Do not special-case the demonstration with hardcoded successful output.

---

## 18. Turn the implementation into a professional portfolio

### 18.1 Root README

Aim for approximately 400–700 useful words, plus the project table. Put the first successful demo command near the top. Link detailed explanations instead of copying ten architecture documents into the root.

The README should contain:

1. A precise one-paragraph description of the repository.
2. A ten-project table with purpose, core mechanism, demo link/command, and verified status.
3. Three featured entry points for a technical reviewer.
4. Installation prerequisites and a minimal doctor/setup/demo sequence.
5. Links to architecture decisions, benchmark evidence, case studies, and supported platforms.
6. An accurate implementation status and licensing/provenance link.

Use actual CI badges sparingly. Do not add invented users, companies, uptime, throughput, stars, adoption, client logos, testimonials, or years of employment. Do not label unfinished projects production-ready.

Recommended first-page features for a backend-focused portfolio are Anchor, Meridian, and Quarry. PyTrace demonstrates language tooling depth; Resonance supplies a memorable music-related demonstration. This is a curation recommendation, not a claim about employer demand or a guarantee of hiring.

### 18.2 Project README and case study

Each project README should answer:

- What problem does this solve, and for whom?
- Which difficult mechanism did the author implement?
- What do the libraries supply?
- How can a reviewer run the smallest meaningful demonstration?
- Which failure can the reviewer trigger deliberately?
- Where are the architecture, benchmarks, and limitations?

Each docs/CASE_STUDY.md should include one real engineering story, not marketing prose:

~~~text
Problem and constraints
Core implementation and ownership
Alternative considered and why it was rejected
Specific defect or design mistake discovered
Reproduction of that defect
Fix and independently meaningful regression evidence
Actual benchmark or evaluation result
What the result does and does not establish
Remaining limits and next justified improvement
~~~

Use diagrams when relationships are easier to understand visually. Keep them focused on transaction boundaries, checkpoint publication, data lineage, control flow, or deployment generations. A diagram must match the code at the cited revision.

### 18.3 Demonstration assets

Produce small authentic captures of the actual software:

- Anchor: recoverable workflow timeline.
- Strata: snapshot/compaction/recovery inspection output.
- Current: watermark and late-event disposition timeline.
- Meridian: journal audit and reconciliation ambiguity view.
- Quarry: incremental plan and historical snapshot comparison.
- PyTrace: source-to-sink trace plus a conservative patch preview.
- Atlas: ranked, attributed, authorized search results.
- Proving Ground: lineage, evaluation, promotion/rollback evidence.
- Routecraft: feasible route map and vehicle timeline.
- Resonance: playable pitch/onset/reference alignment report.

Screenshots and generated charts must come from real demo runs. A static image of a success state is supporting presentation material; the executable demonstration remains required. Keep all user-facing figures readable, labeled, and connected to input/run provenance.

### 18.4 Reviewer paths

docs/PORTFOLIO_GUIDE.md should offer several short routes:

| Reviewer interest | Suggested sequence |
| --- | --- |
| Python backend and reliability | Meridian → Anchor → Current |
| Data engineering | Quarry → Current → Proving Ground |
| Algorithms and systems | Strata → PyTrace → Routecraft |
| Search and applied ML | Atlas → Proving Ground → Resonance |
| Distinctive personal project | Resonance, with audio demo and numerical evaluation |

For each path, name a specific source module and a difficult test to inspect. Do not require the reader to review the entire monorepo to understand one project's contribution.

Include a brief “explain it in an interview” guide per project: the main invariant, one tradeoff, one measured bottleneck, one failure case, and one credible next step. The owner should be able to reproduce and explain those points.

---

## 19. Execution phases and persistence

Progress is gated by working results, not elapsed time or line counts.

| Phase | Coordinator work | Each implementation agent | Exit evidence |
| --- | --- | --- | --- |
| P0 — Inspect and bootstrap | Preserve repo state, establish ownership/commands/CI, inspect capacity | Receive complete assignment | Valid structure, honest status, actual workers launched |
| P1 — First working slice | Integrate packaging and command contracts | Build one real end-to-end core scenario | Each project runs meaningful behavior |
| P2 — Required depth | Resolve shared requests and review invariants | Implement the rest of its required feature contract | All required interfaces and mechanisms exist |
| P3 — Failures and correctness | Independent review and stable-snapshot checks | Fix adversarial/property/integration failures | All project acceptance gates pass |
| P4 — Measurement and operations | Schedule resource-bounded benchmarks | Profile, improve justified bottlenecks, verify restore/runbooks | Reproducible measurements and operational evidence |
| P5 — Integration and presentation | Build IN-01–IN-03, curate root docs, full CI | Fix integration defects and finish case studies | Full portfolio is reviewable and independently runnable |
| P6 — Final verification and handoff | Validate committed snapshot, synchronize authorized Git work, report status | Submit final evidence-backed handoff | Global gates closed or exact external blockers named |

The ten agents may reach phases at different times. Do not hold an independent project idle because another is behind. A completed worker may review another project through read-only inspection and send findings; ownership transfers require a coordinator decision and an explicit write handoff.

### 19.1 Continuous execution loop

Repeat:

Inspect the current gate, select the smallest meaningful implementation or fix, implement within owned paths, run relevant verification, inspect actual results, and fix failures. Update evidence/status, hand off a stable slice, and continue to the next incomplete required gate.

Avoid endless broad retesting after a gate is already sufficiently verified. Rerun affected gates after meaningful changes and complete the next necessary work.

### 19.2 Checkpoints and resumability

Before an unavoidable session/resource stop, write a useful checkpoint:

~~~text
Project and source revision/digest:
Files currently being edited:
Completed acceptance IDs and evidence paths:
Remaining required IDs:
Exact failing command and concise failure:
Required external capability, if any:
Next implementation step:
How to restart the local services:
Git state already verified by coordinator:
~~~

Save generated-but-expensive-to-reproduce run artifacts through the environment's appropriate durable mechanism. Keep the repository's code and small evidence synchronized through Git according to authorization; do not rely on a transient terminal session as the only copy.

On resumption, inspect the checkpoint and the actual repository before acting. Continue unfinished work. Do not recreate completed projects, overwrite newer edits, or replay old assumptions.

### 19.3 What can legitimately block completion

A missing service binary can often be addressed by project-local setup or a supported local installation. A temporarily failed dependency download should be diagnosed and retried reasonably. An implementation bug is work to fix, not an external blocker.

Missing essential credentials, unavailable required execution capabilities, a hard runtime limit, a repository protection/access restriction, or user cancellation may block a specific gate. Record evidence of the blocker, continue independent work, and report what remains.

If the runtime cannot run PostgreSQL, mock tests do not close PostgreSQL concurrency gates. If only three workers fit, keep all ten roles but report three active workers. If a push is rejected, do not claim remote synchronization. If work stops, do not claim it continues invisibly.

---

## 20. Final acceptance and handoff contract

Before declaring the requested implementation complete, the coordinator must verify all of the following.

### 20.1 Code and behavior

- All ten original cores exist and are substantial enough to explain and review.
- All 80 named project acceptance gates pass on their declared required environments.
- All three integration demonstrations pass through public interfaces.
- No mandatory route or command is a placeholder, canned response, no-op, or hidden mock.
- Public interfaces and persisted formats have explicit documented semantics.
- All required code is installed/tested as packages, not only run directly from source.
- Defects found in independent review have regression evidence.

### 20.2 Evidence and reproducibility

- G01–G12 are evaluated individually.
- Every claimed result has its actual command, input, source snapshot, environment, and output.
- Required CI jobs pass on the verified revision; missing remote CI is reported separately.
- Benchmark and numerical-evaluation claims match the actual artifacts.
- At least one clean verification snapshot can reproduce every project's small demo.
- Full workloads can be generated from recorded inputs; large outputs are not required in Git.
- No test exclusion hides a missing required environment or broken mandatory behavior.
- Required numeric tolerances were set before evaluating the held-out fixture set.

### 20.3 Repository and presentation

- Root navigation, ten project READMEs, case studies, architecture decisions, and runbooks are coherent.
- Every advertised command and local evidence link resolves.
- Demo services use isolated owned state and clean up their processes.
- Dependency locks, interpreter declarations, and matrix configuration agree.
- License/provenance statements match actual files.
- Generated noise, caches, secrets, unrelated files, and bulky runtime state are excluded.
- The coordinator has reviewed the intended final diff and commit history.
- No authorized intended development remains accidentally uncommitted.
- Local/remote commit identity and CI status are described accurately.

### 20.4 Final implementation response format

The executing agent's final response should provide:

1. The repository URL and exact final integration commit.
2. A ten-row table: project, completion state, one demo command, evidence path.
3. The outcomes of G01–G12 and IN-01–IN-03.
4. The most meaningful actual benchmark/evaluation results, with their limits.
5. The three best reviewer starting points and why.
6. Exact unresolved external blockers or unsupported scenarios, if any.
7. Whether the work is committed, pushed, and verified by remote CI as distinct facts.

Do not replace this with “all done, production ready” or an ungrounded percentage. Completion is a verifiable state of the repository.

---

## 21. Copy-paste launch prompt

Place this Markdown brief at the repository root as PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md, then give the coordinating development agent this prompt. The /goal prefix is for an agent environment that supports it; otherwise paste the text after the prefix as an ordinary instruction.

~~~text
/goal Work in https://github.com/cheshmakzanoon-ops/python-projects.git.
Read PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md completely and implement
its full required scope: ten substantial Python portfolio projects,
their packaging, real demos, failure tests, benchmarks, documentation,
CI, and three integration demonstrations.

Act as coordinator and launch ten specialist coding agents A01–A10
concurrently after the brief's small bootstrap. Give each its exact
project directory, common standards, and complete project specification.
Ten workers plus the coordinator need eleven slots; if the runtime has
fewer, disclose its real limit and run the maximum supported number,
keeping all ten assignments. Never pretend queued roles are active agents.

Preserve existing work. Use main and explicit directory ownership.
Only the coordinator edits root/shared files or mutates Git. Workers
own only their project directories and independent uv environments/locks.
Pause the relevant writers for stable handoffs, and pause everyone before
any operation that reconciles remote changes into the shared checkout.

Build the original algorithms/domain cores specified in the brief.
Do not substitute wrappers, stubs, canned output, screenshots, excessive
infrastructure, or generated boilerplate for functioning implementations.
Run real PostgreSQL/process/persistence/numerical checks where required.
Use independent reference models and reproduce failures before fixing them.
Record actual measurements with source and environment provenance.

Continue implementing, reviewing, fixing, and verifying until all 80
project acceptance gates, IN-01–IN-03, and G01–G12 are satisfied.
Complete ordinary implementation decisions without asking me repeatedly.
Commit and push coherent verified work to main through the authorized
repository access, preserving protections and existing history.
Do not deploy publicly, publish packages, purchase services, or send
messages as part of this task.

If an essential external constraint blocks one gate, document the exact
failure and continue all independent work. Never fake a pass, reduce
required scope silently, or claim background work after the runtime stops.
Before a hard stop, write a precise resumable checkpoint.
Finish with the final commit, ten-project status, working demo commands,
real verification/benchmark evidence, and accurate push/CI status.
~~~

---

## 22. Technical references and source notes

These references support the underlying tooling and engineering concepts. The project names, ownership model, feature boundaries, workloads, test IDs, and completion criteria are design decisions in this brief. They are not claims that the referenced products endorse this portfolio.

Official documentation was consulted during preparation. The executing agent must recheck exact supported versions and command syntax at implementation time. Do not copy framework implementations into the original cores.

| ID | Primary reference | Supports |
| --- | --- | --- |
| [S01] | Python Developer's Guide: status of Python versions | Supported interpreter lifecycle and version selection |
| [S02] | uv: using workspaces | Shared resolution/lock behavior and independent-project alternative |
| [S03] | uv: locking and syncing | Lock freshness, --locked, --frozen, repeatable installation |
| [S04] | Python typing documentation | Type-system interfaces and runtime-validation distinction |
| [S05] | Python asyncio task documentation | Task groups, cancellation, structured asynchronous work |
| [S06] | pytest good integration practices | src layout, importlib mode, installed-package checks |
| [S07] | Hypothesis stateful testing | Generated operation sequences and reference-model testing |
| [S08] | GitHub Actions job matrices | Project/interpreter matrix execution |
| [S09] | GitHub Actions secure-use reference | Permissions, untrusted input handling, pinned Actions |
| [S10] | Temporal workflow definitions | Deterministic command replay and external activities |
| [S11] | PostgreSQL SELECT documentation | Row locking and SKIP LOCKED queue semantics |
| [S12] | LevelDB implementation notes | LSM tables, manifests, compaction, recovery concepts |
| [S13] | SQLite atomic commit documentation | Persistence assumptions and crash-testing methodology |
| [S14] | Apache Flink watermark generation | Event-time progress, idleness, watermark interaction |
| [S15] | Apache Flink fault tolerance | Checkpoints, replay, and bounded exactly-once claims |
| [S16] | Django 5.2 release notes | LTS status and interpreter compatibility |
| [S17] | Django database transactions, plus [PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | Transaction boundaries and isolation behavior |
| [S18] | Apache Arrow datasets, plus [DuckDB Parquet](https://duckdb.org/docs/current/data/parquet/overview) | Bounded columnar processing and Parquet query primitives |
| [S19] | Python AST, plus [LibCST metadata](https://libcst.readthedocs.io/en/latest/metadata.html) and [codemods](https://libcst.readthedocs.io/en/latest/codemods.html) | Grammar, source structure, scope metadata, formatting-aware transformations |
| [S20] | OASIS SARIF 2.1.0 with Errata 01; [official schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json) | Static-analysis interchange format and schema validation |
| [S21] | Stanford Introduction to Information Retrieval: Okapi BM25 | Term-frequency and document-length ranking concepts |
| [S22] | scikit-learn common pitfalls | Preprocessing consistency and data-leakage prevention |
| [S23] | scikit-learn model persistence | Artifact format trust and version compatibility |
| [S24] | OR-Tools CP-SAT solver documentation | Distinguishing optimal, feasible, infeasible, and unknown outcomes |
| [S25] | SciPy ShortTimeFFT documentation | Windowed transforms, reconstruction, and boundary treatment |
| [S26] | de Cheveigné and Kawahara, “YIN, a fundamental frequency estimator for speech and music,” JASA 111, 1917–1930 (2002) | Original pitch-estimation method; DOI 10.1121/1.1458024 |
| [S27] | Ruff configuration documentation | Explicit parent configuration extension |

[S01]: https://devguide.python.org/versions/
[S02]: https://docs.astral.sh/uv/concepts/projects/workspaces/
[S03]: https://docs.astral.sh/uv/concepts/projects/sync/
[S04]: https://docs.python.org/3.13/library/typing.html
[S05]: https://docs.python.org/3.13/library/asyncio-task.html
[S06]: https://docs.pytest.org/en/stable/explanation/goodpractices.html
[S07]: https://hypothesis.readthedocs.io/en/latest/stateful.html
[S08]: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
[S09]: https://docs.github.com/en/actions/reference/security/secure-use
[S10]: https://docs.temporal.io/workflow-definition
[S11]: https://www.postgresql.org/docs/current/sql-select.html
[S12]: https://github.com/google/leveldb/blob/main/doc/impl.md
[S13]: https://sqlite.org/atomiccommit.html
[S14]: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/event-time/generating_watermarks/
[S15]: https://nightlies.apache.org/flink/flink-docs-stable/docs/learn-flink/fault_tolerance/
[S16]: https://docs.djangoproject.com/en/5.2/releases/5.2/
[S17]: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
[S18]: https://arrow.apache.org/docs/python/dataset.html
[S19]: https://docs.python.org/3.13/library/ast.html
[S20]: https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
[S21]: https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html
[S22]: https://scikit-learn.org/stable/common_pitfalls.html
[S23]: https://scikit-learn.org/stable/model_persistence.html
[S24]: https://developers.google.com/optimization/cp/cp_solver
[S25]: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html
[S26]: https://pubs.aip.org/asa/jasa/article/111/4/1917/547221/YIN-a-fundamental-frequency-estimator-for-speech
[S27]: https://docs.astral.sh/ruff/configuration/

---

**Execution standard:** deliver ten real Python systems that a reviewer can install, challenge, measure, and understand. Close the required gates with evidence, preserve honest limits, and continue until the authorized implementation is complete or a specific external blocker is documented.





