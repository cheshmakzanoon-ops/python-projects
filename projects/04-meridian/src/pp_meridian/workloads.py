"""Seeded fictional equipment-rental demonstration and contention workloads."""

import base64
import json
import random
import resource
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import Client

from pp_meridian.application import ledger, reconcile
from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.evidence import provenance
from pp_meridian.persistence.models import (
    Account,
    Balance,
    Membership,
    Posting,
    StatementRow,
    Tenant,
)
from pp_meridian.reconciliation.assignment import solve
from pp_meridian.reconciliation.candidates import MatchEntry, candidates
from pp_meridian.reconciliation.normalize import normalize_row

_BENCHMARK_SIZES = {
    "ci": (1000, 200, 4, 500),
    "standard": (250000, 10000, 100, 100000),
}


def check_status(checks: dict[str, bool]) -> tuple[str, list[str]]:
    failed = [name for name, passed in checks.items() if not passed]
    return ("failed" if failed else "passed"), failed


def fixture(tenants: int, accounts: int) -> tuple[int, list[Tenant], dict[UUID, list[Account]]]:
    user = get_user_model().objects.create_user(
        username="synthetic-rental-operator", password="local-synthetic-password"
    )
    organizations = [
        Tenant.objects.create(name=f"Fictional equipment rental {i}") for i in range(tenants)
    ]
    result = {}
    for tenant in organizations:
        Membership.objects.create(user=user, tenant=tenant, verified=True)
        result[tenant.id] = [
            ledger.create_account(user.pk, tenant.id, f"account-{i}", "USD")
            for i in range(accounts // tenants)
        ]
    return user.pk, organizations, result


def demo(output: Path, seed: int) -> None:
    before = provenance()
    user, tenants, accounts = fixture(2, 8)
    tenant = tenants[0]
    bank, receivable, income, refund = accounts[tenant.id]
    headers = {
        "HTTP_AUTHORIZATION": "Basic "
        + base64.b64encode(b"synthetic-rental-operator:local-synthetic-password").decode(),
        "HTTP_X_TENANT_ID": str(tenant.id),
    }
    client = Client()
    payload: dict[str, object] = {
        "currency": "USD",
        "reference": "invoice-100",
        "postings": [
            {"account_id": str(receivable.id), "amount": "100.00"},
            {"account_id": str(income.id), "amount": "-100.00"},
        ],
    }

    def request(path: str, data: dict[str, object], key: str) -> dict[str, object]:
        response = client.post(
            path,
            json.dumps(data),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_AUTHORIZATION=headers["HTTP_AUTHORIZATION"],
            HTTP_X_TENANT_ID=headers["HTTP_X_TENANT_ID"],
        )
        if response.status_code != 201:
            raise RuntimeError(response.content.decode())
        return dict(response.json())

    invoice = request("/api/v1/journals", payload, "invoice-100")
    duplicate = request("/api/v1/journals", payload, "invoice-100")
    payment = JournalValue(
        tenant.id, "USD", (Entry(bank.id, 10000), Entry(receivable.id, -10000)), "PAYMENT-100"
    )
    paid = ledger.post(user, payment, "payment-100")
    reversed_invoice = request(
        f"/api/v1/journals/{invoice['id']}/reversal", {}, "reverse-invoice-100"
    )
    ledger.post(
        user,
        JournalValue(
            tenant.id, "USD", (Entry(refund.id, 2500), Entry(bank.id, -2500)), "REFUND-100"
        ),
        "refund-100",
    )
    cad = ledger.create_account(user, tenant.id, "CAD bank", "CAD")
    cad_offset = ledger.create_account(user, tenant.id, "CAD offset", "CAD")
    ledger.post(
        user,
        JournalValue(tenant.id, "CAD", (Entry(cad.id, 100), Entry(cad_offset.id, -100))),
        "cad-payment",
    )

    def transfer(index: int) -> UUID:
        close_old_connections()
        try:
            amount = 100 if index % 2 else -100
            return ledger.post(
                user,
                JournalValue(
                    tenant.id, "USD", (Entry(bank.id, amount), Entry(receivable.id, -amount))
                ),
                f"transfer-{index}",
            ).id
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=8) as pool:
        transfer_ids = list(pool.map(transfer, range(8)))
    rows = [
        {
            "id": f"bank-row-{i}",
            "amount": "100.00",
            "currency": "USD",
            "timestamp": paid.created_at.isoformat(),
            "reference": "PAYMENT100",
        }
        for i in range(2)
    ]
    imported = reconcile.import_rows(user, tenant.id, bank.id, "synthetic-statement", rows)
    repeated = reconcile.import_rows(user, tenant.id, bank.id, "synthetic-statement", rows)
    run = reconcile.run(user, tenant.id, bank.id)
    proposal = run.proposals.get()
    decision = reconcile.decide(user, tenant.id, proposal.id, "approve")
    Balance.objects.filter(account=bank).update(amount=999)
    corrupted = ledger.audit(user, tenant.id)
    ledger.audit(user, tenant.id, rebuild=True)
    verified = ledger.audit(user, tenant.id)
    checks = {
        "duplicate_journal_identical": invoice["id"] == duplicate["id"],
        "reimport_idempotent": imported == repeated
        and len(imported) == len(rows)
        and len(set(imported)) == len(rows),
        "ambiguous_proposal_reviewed": proposal.ambiguous and decision.status == "approved",
        "projection_corruption_detected": corrupted["consistent"] is False,
        "rebuild_consistent": verified["consistent"] is True,
        "concurrent_transfers": len(transfer_ids) == 8 and len(set(transfer_ids)) == 8,
        "linked_reversal": reversed_invoice.get("reversal_of") == invoice["id"],
    }
    status, failed = check_status(checks)
    result = {
        **before,
        "seed": seed,
        "dataset_id": "fictional-equipment-rental-v1",
        "status": status,
        "correctness_checks": checks,
        "failed_checks": failed,
        "invoice": invoice,
        "duplicate_journal_identical": invoice["id"] == duplicate["id"],
        "reversal": reversed_invoice,
        "concurrent_transfers": len(transfer_ids),
        "reimport_idempotent": imported == repeated,
        "reconciliation": run.summary,
        "ambiguous_proposal_reviewed": proposal.ambiguous,
        "projection_corruption_detected": not corrupted["consistent"],
        "rebuild_consistent": verified["consistent"],
        "tenant_id": str(tenant.id),
        "bank_account_id": str(bank.id),
        "audit_diagnostics": {"before_rebuild": corrupted, "after_rebuild": verified},
        "reimport_diagnostics": {
            "first_ids": [str(i) for i in imported],
            "repeated_ids": [str(i) for i in repeated],
        },
    }
    if provenance()["source_content_sha256"] != before["source_content_sha256"]:
        raise RuntimeError("source changed during demo")
    (output / "demo.json").write_text(json.dumps(result, indent=2))
    (output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Meridian demonstration</title><style>body{font:18px system-ui;max-width:70rem;margin:3rem auto}pre{white-space:pre-wrap;background:#f0f3f3;padding:2rem}</style><h1>Fictional equipment-rental ledger</h1><p>Duplicate request, linked reversal, concurrent transfers, ambiguous statement review, and independent balance rebuild.</p><pre>'
        + __import__("html").escape(json.dumps(result, indent=2))
        + "</pre></html>"
    )
    print(
        json.dumps(
            {"status": status, "failed_checks": failed, "report": str(output / "report.html")},
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


def benchmark(output: Path, seed: int, profile: str) -> None:
    before = provenance()
    rng = random.Random(seed)
    count, account_count, tenant_count, row_count = _BENCHMARK_SIZES[profile]
    user, tenants, accounts = fixture(tenant_count, account_count)
    first = tenants[0]
    aa = accounts[first.id]
    ledger.post(
        user, JournalValue(first.id, "USD", (Entry(aa[0].id, 1), Entry(aa[1].id, -1))), "warmup"
    )
    latencies: dict[str, list[float]] = {"same_tenant": [], "many_tenant": []}
    batch_seconds: dict[str, list[float]] = {"same_tenant": [], "many_tenant": []}
    waits = []

    def execute(item: tuple[int, int, int, str]) -> float:
        index, tenant_index, amount, mode = item
        close_old_connections()
        try:
            tenant = tenants[tenant_index]
            aa = accounts[tenant.id]
            offset = (index % (len(aa) // 4)) * 4
            chosen = aa[offset : offset + 4]
            value = JournalValue(
                tenant.id,
                "USD",
                tuple(Entry(a.id, sign * amount) for a, sign in zip(chosen, (1, -1, 1, -1))),
                f"RENTAL-{index}",
            )
            start = time.perf_counter()
            ledger.post(user, value, f"benchmark-{index}")
            return time.perf_counter() - start
        finally:
            close_old_connections()

    def execute_batch(jobs: list[tuple[int, int, int, str]]) -> list[float]:
        # Eight actual clients each reuse a connection, matching persistent API workers.
        connection.settings_dict["CONN_MAX_AGE"] = 600
        try:
            return [execute(job) for job in jobs]
        finally:
            connections.close_all()

    index = 0
    repetitions = 5 if profile == "ci" else 1
    for mode in ["same_tenant", "many_tenant"]:
        for repetition in range(repetitions):
            jobs = []
            for _ in range(count // (2 * repetitions)):
                index += 1
                tenant_index = 0 if mode == "same_tenant" else index % tenant_count
                jobs.append((index, tenant_index, index * 10 + rng.randrange(10), mode))
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=8) as pool:
                for chunk in pool.map(execute_batch, [jobs[i::8] for i in range(8)]):
                    latencies[mode].extend(chunk)
            batch_seconds[mode].append(time.perf_counter() - start)
            waits.append(ledger.lock_waits())
    replay_start = time.perf_counter()
    audit_reports = [(str(t.id), ledger.audit(user, t.id)) for t in tenants]
    audit_results = [report["consistent"] for _, report in audit_reports]
    replay_seconds = time.perf_counter() - replay_start
    posting_rows = list(
        Posting.objects.exclude(journal__reference="")
        .select_related("journal", "account")
        .order_by("journal__sequence", "id")[:row_count]
    )
    import_start = time.perf_counter()
    grouped: dict[UUID, list[dict[str, object]]] = {}
    for row_index, original_posting in enumerate(posting_rows):
        posting = posting_rows[row_index - 1] if row_index % 100 == 99 else original_posting
        amount = posting.amount
        sign = "-" if amount < 0 else ""
        row: dict[str, object] = {
            "id": str(original_posting.id),
            "amount": f"{sign}{abs(amount) // 100}.{abs(amount) % 100:02d}",
            "currency": "USD",
            "timestamp": posting.journal.created_at.isoformat(),
            "reference": posting.journal.reference,
        }
        normalize_row(row)
        grouped.setdefault(posting.account_id, []).append(row)
    normalization_seconds = time.perf_counter() - import_start
    ambiguous_components = 0
    matched_rows = 0
    graph_edges = []
    solver_times = []
    graph_rows = []
    reimport_diagnostics: list[dict[str, object]] = []
    first_import_total = reimport_total = stored_before_total = stored_after_total = 0
    solver_cardinality_valid = True
    for account_id, rows in grouped.items():
        account = Account.objects.get(id=account_id)
        first_ids = []
        for offset in range(0, len(rows), 10000):
            first_ids.extend(
                reconcile.import_rows(
                    user, account.tenant_id, account_id, "benchmark", rows[offset : offset + 10000]
                )
            )
        stored_before = StatementRow.objects.filter(
            account_id=account_id, source="benchmark"
        ).count()
        left = [
            MatchEntry(
                str(r["id"]),
                normalize_row(r).amount,
                "USD",
                normalize_row(r).timestamp,
                str(r["reference"]),
            )
            for r in rows
        ]
        postings = Posting.objects.filter(account_id=account_id).select_related("journal")
        right = [
            MatchEntry(str(p.id), p.amount, "USD", p.journal.created_at, p.journal.reference)
            for p in postings
        ]
        graph = candidates(left, right)
        start = time.perf_counter()
        assignments = solve([r.identity for r in left], graph)
        solver_times.append(time.perf_counter() - start)
        ambiguous_components += sum(a.ambiguous for a in assignments)
        matched_rows += sum(len(a.pairs) for a in assignments)
        graph_edges.append(len(graph))
        graph_rows.append(len(rows))
        solver_cardinality_valid = solver_cardinality_valid and sum(
            len(a.pairs) for a in assignments
        ) <= len(rows)
        # Verify both returned identities and persisted cardinality across reimport.
        repeated_ids = []
        for offset in range(0, len(rows), 10000):
            repeated_ids.extend(
                reconcile.import_rows(
                    user, account.tenant_id, account_id, "benchmark", rows[offset : offset + 10000]
                )
            )
        stored_after = StatementRow.objects.filter(
            account_id=account_id, source="benchmark"
        ).count()
        first_import_total += len(first_ids)
        reimport_total += len(repeated_ids)
        stored_before_total += stored_before
        stored_after_total += stored_after
        if not (
            first_ids == repeated_ids
            and len(first_ids) == len(set(first_ids)) == len(rows)
            and stored_before == stored_after == len(rows)
        ):
            reimport_diagnostics.append(
                {
                    "account_id": str(account_id),
                    "expected_rows": len(rows),
                    "first_ids_count": len(first_ids),
                    "first_ids_unique": len(set(first_ids)),
                    "repeated_ids_count": len(repeated_ids),
                    "identities_equal": first_ids == repeated_ids,
                    "stored_before": stored_before,
                    "stored_after": stored_after,
                }
            )
    checks = {
        "independent_replay": all(value is True for value in audit_results),
        "statement_rows_accounted": sum(graph_rows) == row_count
        and 0 <= matched_rows <= row_count
        and solver_cardinality_valid,
        "controlled_ambiguity_detected": ambiguous_components > 0,
        "stable_reimport": not reimport_diagnostics
        and first_import_total
        == reimport_total
        == stored_before_total
        == stored_after_total
        == row_count,
    }
    status, failed = check_status(checks)
    metrics: dict[str, object] = {
        "replay_seconds": replay_seconds,
        "normalization_rows_per_second": row_count / normalization_seconds,
        "solver_seconds": sum(solver_times),
        "graph_edge_counts": graph_edges,
        "ambiguous_components": ambiguous_components,
        "matched_rows": matched_rows,
        "unmatched_rows": row_count - matched_rows,
        "graph_row_counts": graph_rows,
        "lock_waits_at_batch_boundaries": waits,
        "lock_wait_sampling": "batch-boundary samples; transient lock waits may be missed",
        "retry_rate": ledger.retry_count() / count,
        "retry_rate_explanation": "observed whole-transaction retry counter divided by measured journals",
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    for mode, values in latencies.items():
        ordered = sorted(values)
        metrics[mode] = {
            "journals": len(values),
            "batch_seconds": batch_seconds[mode],
            "throughput_per_second": len(values) / sum(batch_seconds[mode]),
            "latency_p50_seconds": statistics.median(values),
            "latency_p95_seconds": ordered[int(len(values) * 0.95)],
            "latency_max_seconds": max(values),
        }
    result = {
        **before,
        "seed": seed,
        "dataset_id": hashlib_dataset(seed, count),
        "profile": profile,
        "parameters": {
            "journals": count,
            "postings_per_journal": 4,
            "accounts": account_count,
            "tenants": tenant_count,
            "statement_rows": row_count,
            "concurrent_clients": 8,
            "connection_policy": "one persistent PostgreSQL connection per client batch",
            "isolation": "READ COMMITTED with per-tenant sequencing row serialization",
            "durability": "PostgreSQL synchronous_commit default on",
        },
        "warmup_runs": 1,
        "measurement_runs": repetitions,
        "measurement_repetition_policy": "ci: five batches per contention mode; standard: one full 250k-journal workload because repeating million-posting durable workloads five times is costly; per-journal latency distribution retained",
        "metrics": metrics,
        "correctness_checks": checks,
        "failed_checks": failed,
        "audit_diagnostics": [
            {"tenant_id": identity, "audit": report}
            for identity, report in audit_reports
            if report["consistent"] is not True
        ],
        "reimport_diagnostics": {
            "accounts_checked": len(grouped),
            "first_import_rows": first_import_total,
            "reimport_rows": reimport_total,
            "stored_rows_before": stored_before_total,
            "stored_rows_after": stored_after_total,
            "failures": reimport_diagnostics,
        },
        "status": status,
    }
    if provenance()["source_content_sha256"] != before["source_content_sha256"]:
        raise RuntimeError("source changed during benchmark")
    (output / "benchmark.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "status": status,
                "failed_checks": failed,
                "benchmark": str(output / "benchmark.json"),
            },
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


def hashlib_dataset(seed: int, count: int) -> str:
    import hashlib

    return "rental-ledger-v1:" + hashlib.sha256(f"{seed}:{count}:4-postings".encode()).hexdigest()
