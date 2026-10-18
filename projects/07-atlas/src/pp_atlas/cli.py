"""Atlas library/HTTP entry points and reproducible owned demonstrations."""

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from pp_atlas import Document, Engine, Principal
from pp_atlas.evaluation import evaluate, load_corpus, load_judgments

MARKER = ".atlas-owned-output-v1"


def owned_output(path: Path) -> Path:
    """Refuse symlinks, checkout paths, filesystem roots, and unowned directories."""
    original = path.absolute()
    if any(parent.is_symlink() for parent in [original, *original.parents]):
        raise ValueError("output path must not traverse symlinks")
    path = path.resolve()
    project = Path(__file__).resolve().parents[2]
    if (
        path == Path(path.anchor)
        or path == Path.home()
        or path == project
        or project in path.parents
        and ".local" not in path.parts
    ):
        raise ValueError("unsafe output directory")
    marker = path / MARKER
    if (
        path.exists()
        and any(path.iterdir())
        and (not marker.is_file() or marker.read_text() != "atlas-output-v1\n")
    ):
        raise ValueError("output directory contains files not owned by Atlas")
    path.mkdir(parents=True, exist_ok=True)
    marker.write_text("atlas-output-v1\n")
    return path


def clean_output(path: Path) -> None:
    if not path.exists():
        return
    # This validates ownership before touching any child. Only named output files
    # and the state subtree are removed; unexpected user files are preserved.
    path = owned_output(path)
    allowed = {MARKER, "state", "demo.json", "benchmark.json", "evaluation.json"}
    unexpected = {p.name for p in path.iterdir()} - allowed
    if unexpected:
        raise ValueError("refusing cleanup: unexpected files in owned output")
    for child in path.iterdir():
        if child.is_symlink():
            raise ValueError("refusing cleanup of symlink")
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    path.rmdir()


def demo(output: Path, seed: int) -> dict[str, object]:
    engine = Engine(output / "state")
    p = Principal("demo", "alice")
    engine.upsert_many(
        "demo",
        [
            Document(
                "runbook",
                "Recovering the journal",
                'WAL recovery replays committed records. Escape <script>alert("unsafe")</script>.',
                metadata={"type": "runbook"},
            ),
            Document(
                "restricted",
                "Operations drill",
                "WAL recovery secret internal drill",
                frozenset({"group:ops"}),
                {"type": "incident"},
            ),
            Document(
                "design",
                "Journal design",
                "A recovery boundary must be durable. WAL checksums detect incomplete writes.",
                metadata={"type": "design"},
            ),
        ],
    )
    before = engine.search(p, '"wal recovery"')
    engine.set_groups("demo", "alice", ["ops"])
    granted = engine.search(p, '"wal recovery"')
    engine.set_groups("demo", "alice", [])
    revoked = engine.search(p, '"wal recovery"')
    engine.upsert(
        "demo",
        Document(
            "design",
            "Revised journal design",
            "Current revision: checksummed publication is atomic.",
            metadata={"type": "design"},
        ),
    )
    engine.delete("demo", "restricted")
    pre_merge = engine.search(p, "recovery")
    engine.merge("demo")
    after_merge = engine.search(p, "recovery")
    checks = {
        "grant_observed": granted.total == before.total + 1,
        "revoke_observed": revoked.hits == before.hits,
        "obsolete_revision_absent": engine.search(p, '"recovery boundary"').total == 0,
        "merge_scores_preserved": pre_merge.hits == after_merge.hits,
        "escaped_snippet": "<script>" not in after_merge.hits[0].snippet,
    }
    return {
        "schema_version": 1,
        "project": "atlas",
        "seed": seed,
        "query": '"wal recovery"',
        "ranked_authorized_results": asdict(after_merge),
        "checks": checks,
        "catalog": engine.inspect("demo"),
        "status": "passed" if all(checks.values()) else "failed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atlas permission-aware document search")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["demo", "benchmark", "clean-demo"]:
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name != "clean-demo":
            command.add_argument("--seed", type=int, default=1729)
        if name == "benchmark":
            command.add_argument("--profile", choices=["ci", "standard"], default="ci")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--root", type=Path, required=True)
    evaluate_parser.add_argument("--corpus", type=Path, required=True)
    evaluate_parser.add_argument("--judgments", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path, required=True)
    for name in [
        "ingest",
        "search",
        "fetch",
        "delete",
        "acl",
        "groups",
        "inspect",
        "merge",
        "serve",
    ]:
        command = sub.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
        if name != "serve":
            command.add_argument("--tenant", required=True)
        if name in ["search", "fetch"]:
            command.add_argument("--subject", required=True)
        if name == "search":
            command.add_argument("query")
            command.add_argument("--limit", type=int, default=10)
        if name in ["fetch", "delete", "acl"]:
            command.add_argument("id")
        if name == "ingest":
            command.add_argument("--input", type=Path, required=True)
        if name == "acl":
            command.add_argument("--allow", action="append", default=[])
        if name == "groups":
            command.add_argument("--subject", required=True)
            command.add_argument("--group", action="append", default=[])
        if name == "serve":
            command.add_argument("--port", type=int, default=8107)
    args = parser.parse_args(argv)
    try:
        if args.command == "clean-demo":
            clean_output(args.output)
            return 0
        report: object
        if args.command in ["demo", "benchmark"]:
            output = owned_output(args.output)
            if (output / "state").exists():
                raise ValueError("state already exists; clean-demo before rerunning")
            if args.command == "demo":
                report = demo(output, args.seed)
            else:
                from pp_atlas.benchmarks import run_benchmark

                report = run_benchmark(
                    Path(__file__).resolve().parents[2], output, args.profile, args.seed
                )
            (output / f"{args.command}.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            )
        elif args.command == "evaluate":
            from pp_atlas.provenance import provenance

            source = provenance(Path(__file__).resolve().parents[2])
            engine = Engine(args.root)
            engine.upsert_many("quality", load_corpus(args.corpus))
            judgments = load_judgments(args.judgments)
            report = {
                "schema_version": 1,
                "project": "atlas",
                **source,
                "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
                "judgments_sha256": hashlib.sha256(args.judgments.read_bytes()).hexdigest(),
                "baseline": evaluate(
                    engine, Principal("quality", "public"), judgments, baseline=True
                ),
                "improved": evaluate(engine, Principal("quality", "public"), judgments),
            }
            if args.output.exists():
                raise ValueError("refusing to overwrite evaluation output")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        elif args.command == "serve":
            import uvicorn

            from pp_atlas.api import Identity, create_app

            bindings = json.loads(os.environ.get("ATLAS_TOKEN_BINDINGS", "{}"))
            tokens = {
                token: Identity(
                    Principal(value["tenant"], value["subject"]), value.get("admin", False)
                )
                for token, value in bindings.items()
            }
            uvicorn.run(create_app(Engine(args.root), tokens), host="127.0.0.1", port=args.port)
            return 0
        else:
            engine = Engine(args.root)
            if args.command == "ingest":
                if args.input.stat().st_size > 20_000_000:
                    raise ValueError("input exceeds 20MB")
                report = engine.upsert_many(args.tenant, load_corpus(args.input))
            elif args.command == "search":
                report = asdict(
                    engine.search(
                        Principal(args.tenant, args.subject), args.query, limit=args.limit
                    )
                )
            elif args.command == "fetch":
                document = engine.fetch(Principal(args.tenant, args.subject), args.id)
                report = {
                    "id": document.id,
                    "title": document.title,
                    "text": document.text,
                    "metadata": document.metadata,
                }
            elif args.command == "delete":
                report = {"deleted": engine.delete(args.tenant, args.id)}
            elif args.command == "acl":
                engine.set_acl(args.tenant, args.id, args.allow)
                report = {"updated": True}
            elif args.command == "groups":
                engine.set_groups(args.tenant, args.subject, args.group)
                report = {"updated": True}
            elif args.command == "merge":
                report = {"generation": engine.merge(args.tenant)}
            else:
                report = engine.inspect(args.tenant)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if isinstance(report, dict) and report.get("status") == "failed" else 0
    except (ValueError, KeyError, OSError, RuntimeError) as error:
        print(f"Atlas: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
