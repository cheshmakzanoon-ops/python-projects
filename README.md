# Python systems portfolio

Ten independent Python products exploring durable workflows, storage, streaming, accounting, analytical data, language tooling, search, ML operations, optimization, and guitar audio. Each product owns an original Python engineering core, an installable package, an isolated dependency lock, executable demonstrations, failure tests, and operational documentation. The [master execution brief](PYTHON_PORTFOLIO_MASTER_EXECUTION_BRIEF.md) defines the acceptance contracts; [verified status](docs/STATUS.md) records local acceptance and the separate hosted CI observation.

Start with Current's local event-time demonstration; it needs no database service:

```sh
python scripts/portfolio.py setup current
python scripts/portfolio.py demo current
python scripts/portfolio.py clean-demo current
```

Use uv 0.12.23 and standard CPython 3.13 or 3.14. The selected project installs its pinned default interpreter and dependencies through uv. `python scripts/portfolio.py list` shows the products; `doctor` checks the bootstrap prerequisites. See [development instructions](CONTRIBUTING.md) for cloud cache paths, PostgreSQL setup, and explicit interpreter selection.

| Project | Original mechanism | Small demo | State |
| --- | --- | --- | --- |
| [Anchor](projects/01-anchor/) | Durable reducer/replay, PostgreSQL leases, fenced compensation | `demo anchor` | Local acceptance passed |
| [Strata](projects/02-strata/) | Framed WAL, skip-list memtable, SSTables, MVCC/compaction | `demo strata` | Local acceptance passed |
| [Current](projects/03-current/) | Ordered ingress, watermarks, windows/joins, checkpoint/outbox | `demo current` | Local acceptance passed |
| [Meridian](projects/04-meridian/) | Double-entry constraints, tenant sequencing, min-cost reconciliation | `demo meridian` | Local acceptance passed |
| [Quarry](projects/05-quarry/) | Version/tombstone registry, partition-local DAGs, pinned Parquet snapshots | `demo quarry` | Local acceptance passed |
| [PyTrace](projects/06-pytrace/) | CFG/fixed-point dataflow and conservative LibCST edits | `demo pytrace` | Local acceptance passed |
| [Atlas](projects/07-atlas/) | Positional indexing, visible-set BM25, ACL-aware generations | `demo atlas` | Local acceptance passed |
| [Proving Ground](projects/08-proving-ground/) | Leakage contracts, bound promotion decisions, serving generations | `demo proving-ground` | Local acceptance passed |
| [Routecraft](projects/09-routecraft/) | Regret insertion, adaptive search, independent route verification | `demo routecraft` | Local acceptance passed |
| [Resonance](projects/10-resonance/) | YIN pitch, onset decoding, chunk equivalence, score alignment | `demo resonance` | Local acceptance passed |

Prefix table commands with `python scripts/portfolio.py`. All 80 project acceptance IDs, ten standard workloads and three integrations have local passing evidence on their declared Linux environment. The compatibility matrix records 1,136 project test executions across CPython 3.13.16 and 3.14.8, plus isolated installed-wheel demos. Hosted CI remains separately unverified; see the [evidence index](docs/evidence/README.md). Every demo writes isolated owned state under `.local/`; cleanup targets only the selected product's demo. Required PostgreSQL workflows use separate local databases. Core behavior runs offline after dependency installation, without paid APIs, a GPU, or cloud credentials.

For a focused technical review, start with Anchor's event/command reducer and stale-worker tests, Current's independent event/control oracle, or Quarry's exact historical-version registry and publication-failure tests. The [reviewer guide](docs/PORTFOLIO_GUIDE.md) offers routes by interest. Product case studies explain actual defects and tradeoffs; benchmark documents separate authored correctness fixtures from generated scale inputs. Performance claims must name their source revision, workload, repetitions, and machine conditions.

The products communicate only through documented files or HTTP contracts. Coordinator-owned demonstrations cover recoverable settlement, late stream corrections into historical lake snapshots, and authorized search of code-analysis findings. See [repository architecture](docs/architecture/REPOSITORY.md) and the [evidence policy](docs/architecture/EVIDENCE.md). Local success, a Git push, and remote CI success are reported separately. Full durability and process-fault suites currently require Linux; other platform combinations remain unverified.

No code license has been selected by the owner. [Provenance and notices](THIRD_PARTY_NOTICES.md) identify this status and the use of original synthetic fixtures. These implementations and measurements are portfolio work; they do not claim customer deployments, employment history, or production operating experience.
