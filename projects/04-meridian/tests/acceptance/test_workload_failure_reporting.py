"""Public commands must reject actual correctness failures after writing evidence."""

import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection

from pp_meridian import cli, workloads
from pp_meridian.persistence.models import Balance, StatementRow

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("fault", ["audit", "identity", "row_count", None])
def test_benchmark_cli_checks_real_audits_and_reimport_results(monkeypatch, tmp_path, fault):
    # Keep the production loop, PostgreSQL transactions, solver and reporting path;
    # shrink only generated dimensions so failure tests are not performance runs.
    monkeypatch.setitem(workloads._BENCHMARK_SIZES, "ci", (40, 16, 4, 100))
    monkeypatch.setitem(connection.settings_dict, "CONN_MAX_AGE", 0)
    monkeypatch.setattr(cli, "initialize", lambda output: {})
    output = tmp_path / "benchmark"
    monkeypatch.setattr(
        sys, "argv", ["meridian", "benchmark", "--profile", "ci", "--output", str(output)]
    )
    real_audit = workloads.ledger.audit
    audit_calls = 0

    def audited(user, tenant, rebuild=False):
        nonlocal audit_calls
        audit_calls += 1
        if fault == "audit" and audit_calls == 1:
            projection = Balance.objects.filter(account__tenant_id=tenant).first()
            Balance.objects.filter(account_id=projection.account_id).update(
                amount=projection.amount + 1
            )
        return real_audit(user, tenant, rebuild)

    monkeypatch.setattr(workloads.ledger, "audit", audited)
    real_import = workloads.reconcile.import_rows
    seen = set()
    injected = False

    def imported(user, tenant, account, source, rows):
        nonlocal injected
        result = real_import(user, tenant, account, source, rows)
        key = account, tuple(row["id"] for row in rows)
        if key in seen and not injected:
            if fault == "identity":
                result[0] = uuid4()
                injected = True
            elif fault == "row_count":
                existing = StatementRow.objects.get(id=result[0])
                StatementRow.objects.create(
                    account_id=account,
                    source=source,
                    identity="injected-extra-row",
                    payload_hash="0" * 64,
                    amount=existing.amount,
                    currency=existing.currency,
                    timestamp=existing.timestamp,
                    reference=existing.reference,
                )
                injected = True
        seen.add(key)
        return result

    monkeypatch.setattr(workloads.reconcile, "import_rows", imported)
    if fault is None:
        cli.main()
    else:
        with pytest.raises(SystemExit) as failure:
            cli.main()
        assert failure.value.code == 1
    report = json.loads((output / "benchmark.json").read_text())
    assert report["parameters"]["journals"] == 40
    assert report["parameters"]["statement_rows"] == 100
    assert report["status"] == ("passed" if fault is None else "failed")
    expected_failure = "independent_replay" if fault == "audit" else "stable_reimport"
    if fault is not None:
        assert expected_failure in report["failed_checks"]
        assert report["correctness_checks"][expected_failure] is False
    else:
        assert report["failed_checks"] == []
        assert all(report["correctness_checks"].values())
    if fault == "audit":
        assert report["audit_diagnostics"][0]["audit"]["differences"]
    if fault == "identity":
        assert report["reimport_diagnostics"]["failures"][0]["identities_equal"] is False
    if fault == "row_count":
        diagnostics = report["reimport_diagnostics"]
        assert diagnostics["stored_rows_after"] == diagnostics["stored_rows_before"] + 1


@pytest.mark.parametrize("fault", ["audit", "duplicate"])
def test_demo_cli_rejects_bad_rebuild_or_duplicate_identity(monkeypatch, tmp_path, fault):
    monkeypatch.setattr(cli, "initialize", lambda output: {})
    output = tmp_path / "demo"
    monkeypatch.setattr(sys, "argv", ["meridian", "demo", "--output", str(output)])
    real_audit = workloads.ledger.audit
    audit_calls = 0

    def audited(user, tenant, rebuild=False):
        nonlocal audit_calls
        audit_calls += 1
        if fault == "audit" and audit_calls == 3:
            projection = Balance.objects.filter(account__tenant_id=tenant).first()
            Balance.objects.filter(account_id=projection.account_id).update(
                amount=projection.amount + 1
            )
        return real_audit(user, tenant, rebuild)

    monkeypatch.setattr(workloads.ledger, "audit", audited)
    real_post = workloads.Client.post
    invoice_requests = 0

    def post(client, path, *args, **kwargs):
        nonlocal invoice_requests
        response = real_post(client, path, *args, **kwargs)
        if kwargs.get("HTTP_IDEMPOTENCY_KEY") == "invoice-100":
            invoice_requests += 1
            if fault == "duplicate" and invoice_requests == 2:
                payload = response.json()
                payload["id"] = str(uuid4())
                return SimpleNamespace(
                    status_code=201, content=json.dumps(payload).encode(), json=lambda: payload
                )
        return response

    monkeypatch.setattr(workloads.Client, "post", post)
    with pytest.raises(SystemExit) as failure:
        cli.main()
    assert failure.value.code == 1
    report = json.loads((output / "demo.json").read_text())
    assert report["status"] == "failed"
    expected_failure = "rebuild_consistent" if fault == "audit" else "duplicate_journal_identical"
    assert expected_failure in report["failed_checks"]
    assert report["correctness_checks"][expected_failure] is False
    assert (output / "report.html").is_file()
