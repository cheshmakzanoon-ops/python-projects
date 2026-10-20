"""Own the local ledger HTTP server while a separate Anchor environment recovers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def anchor_environment(root: Path, interpreter: str) -> dict[str, str]:
    """The nested participant must not inherit Meridian's selected environment."""
    environment = os.environ.copy()
    for name in (
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        environment.pop(name, None)
    directory = root / "projects/01-anchor"
    default = (directory / ".python-version").read_text().strip()
    environment.update(UV_PROJECT=str(directory), UV_WORKING_DIR=str(directory))
    environment["UV_PROJECT_ENVIRONMENT"] = str(
        directory / ".venv"
        if interpreter == default
        else root / ".local/venvs" / f"anchor-{interpreter}"
    )
    environment["PORTFOLIO_PYTHON"] = interpreter
    return environment


def run(output: Path) -> None:
    from pp_meridian.cli import clean, initialize

    ledger_output = output / "ledger"
    ledger_output.mkdir()
    initialize(ledger_output)
    from django.contrib.auth import get_user_model
    from django.core.wsgi import get_wsgi_application
    from django.db import connections
    from pp_meridian.application.ledger import audit, create_account
    from pp_meridian.persistence.models import Journal, Membership, Posting, Tenant

    tenant = Tenant.objects.create(name="Synthetic settlement integration")
    username, password = "settlement-fixture", "local-synthetic-fixture-only"
    user = get_user_model().objects.create_user(username=username, password=password)
    Membership.objects.create(user=user, tenant=tenant, verified=True)
    debit = create_account(user.pk, tenant.pk, "Simulated bank", "CAD")
    credit = create_account(user.pk, tenant.pk, "Simulated clearing", "CAD")
    server = make_server("127.0.0.1", 0, get_wsgi_application(), handler_class=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    configuration = {
        "base_url": f"http://127.0.0.1:{server.server_port}",
        "tenant_id": str(tenant.pk),
        "username": username,
        "password": password,
        "journal": {
            "currency": "CAD",
            "reference": "synthetic-settlement",
            "postings": [
                {"account_id": str(debit.pk), "amount": "12.34"},
                {"account_id": str(credit.pk), "amount": "-12.34"},
            ],
        },
    }
    (output / "local-connection.json").write_text(json.dumps(configuration))
    root = Path(__file__).resolve().parents[2]
    interpreter = (
        os.environ.get("PORTFOLIO_PYTHON")
        or (root / "projects/01-anchor/.python-version").read_text().strip()
    )
    command = ["uv", "run", "--locked", "--python", interpreter]
    command += ["python", str(Path(__file__).with_name("anchor_stage.py")), "--output", str(output)]
    try:
        subprocess.run(
            command,
            cwd=root / "projects/01-anchor",
            env=anchor_environment(root, interpreter),
            check=True,
            timeout=180,
        )
        anchor = json.loads((output / "anchor-evidence.json").read_text())
        journals = list(Journal.objects.filter(tenant=tenant).order_by("sequence"))
        assert len(journals) == 3, "one successful posting plus one reversed posting pair"
        assert sum(j.reversal_of_id is not None for j in journals) == 1
        for journal in journals:
            amounts = list(Posting.objects.filter(journal=journal).values_list("amount", flat=True))
            assert len(amounts) == 2 and sum(amounts) == 0
        by_reference = {str(j.id): j for j in journals}
        assert anchor["first_journal_id"] in by_reference
        assert audit(user.pk, tenant.pk)["consistent"]
        # Independent accumulation from immutable SQL postings, without balance projection helpers.
        totals = {str(debit.pk): 0, str(credit.pk): 0}
        for account, amount in Posting.objects.filter(journal__tenant=tenant).values_list(
            "account_id", "amount"
        ):
            totals[str(account)] += amount
        assert totals == {str(debit.pk): 1234, str(credit.pk): -1234}
        report = {
            "journal_ids": [str(j.pk) for j in journals],
            "journal_count": 3,
            "reversal_count": 1,
            "all_journals_balanced": True,
            "independent_balances_minor_units": totals,
            "projection_audit_consistent": True,
        }
        (output / "meridian-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        connections.close_all()
        # Local credentials are synthetic but still need not be retained in evidence.
        (output / "local-connection.json").unlink(missing_ok=True)
        clean(ledger_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
