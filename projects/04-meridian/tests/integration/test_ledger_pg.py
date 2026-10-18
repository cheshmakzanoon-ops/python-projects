import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client

from pp_meridian.application import ledger as service
from pp_meridian.application import reconcile
from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.persistence.models import (
    Account,
    ApprovedMatch,
    Balance,
    Idempotency,
    Journal,
    Membership,
    Posting,
    Proposal,
    StatementRow,
    Tenant,
)

pytestmark = pytest.mark.django_db(transaction=True)


def journal_value(ledger, amount=100):
    user, tenant, accounts = ledger
    return JournalValue(
        tenant.id, "USD", (Entry(accounts[0].id, amount), Entry(accounts[1].id, -amount)), "INV-100"
    )


def parallel(function, inputs):
    def run(value):
        close_old_connections()
        try:
            return function(value)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(run, inputs))


def test_me02_concurrent_lost_response_canonical_idempotency(ledger):
    user, tenant, accounts = ledger
    value = journal_value(ledger)
    ids = parallel(lambda _: service.post(user, value, "same").id, range(8))
    assert len(set(ids)) == 1
    reordered = JournalValue(tenant.id, "USD", tuple(reversed(value.entries)), value.reference)
    assert service.post(user, reordered, "same").id == ids[0]
    with pytest.raises(service.Conflict):
        service.post(user, journal_value(ledger, 200), "same")
    assert Journal.objects.count() == Idempotency.objects.count() == 1
    assert Balance.objects.get(account=accounts[0]).amount == 100


def test_me03_opposite_transfers_commit_prefix(ledger):
    user, tenant, accounts = ledger

    def transfer(i):
        value = journal_value(ledger, 100 if i % 2 else -100)
        return service.post(user, value, f"transfer-{i}").sequence

    sequences = parallel(transfer, range(40))
    assert sorted(sequences) == list(range(1, 41))
    assert service.balance(user, tenant.id, accounts[0].id) == 0
    assert service.audit(user, tenant.id)["consistent"]
    assert all(
        sum(
            Posting.objects.filter(journal__tenant=tenant, journal__sequence__lte=s).values_list(
                "amount", flat=True
            )
        )
        == 0
        for s in sequences
    )


def test_me04_atomic_fault_and_direct_database_constraints(ledger):
    user, tenant, accounts = ledger

    def fail():
        raise RuntimeError("interrupt posting")

    with pytest.raises(RuntimeError):
        service.post(user, journal_value(ledger), "failed", fault=fail)
    assert Journal.objects.count() == Posting.objects.count() == Idempotency.objects.count() == 0
    assert all(a == 0 for a in Balance.objects.values_list("amount", flat=True))
    journal = service.post(user, journal_value(ledger), "valid")
    posting = journal.postings.first()
    mutations = [
        lambda: Journal.objects.filter(id=journal.id).update(reference="tamper"),
        lambda: Posting.objects.filter(id=posting.id).update(amount=999),
        lambda: Posting.objects.filter(id=posting.id).delete(),
        lambda: Account.objects.filter(id=accounts[0].id).update(currency="CAD"),
        lambda: Posting.objects.create(journal=journal, account=accounts[2], amount=1),
    ]
    for mutation in mutations:
        with pytest.raises(IntegrityError), transaction.atomic():
            mutation()
    with pytest.raises(IntegrityError), transaction.atomic():
        j = Journal.objects.create(tenant=tenant, currency="USD")
        Posting.objects.create(journal=j, account=accounts[0], amount=1)
        Posting.objects.create(journal=j, account=accounts[1], amount=-2)
    with pytest.raises(IntegrityError), transaction.atomic():
        Journal.objects.create(tenant=tenant, currency="USD")
    assert Journal.objects.count() == 1


def test_database_rejects_cross_tenant_currency_and_invalid_reversal(ledger):
    user, tenant, accounts = ledger
    other = Tenant.objects.create(name="Other")
    foreign = Account.objects.create(tenant=other, name="other", currency="USD")
    cad = service.create_account(user, tenant.id, "CAD", "CAD")
    for account in [foreign, cad]:
        with pytest.raises(IntegrityError), transaction.atomic():
            j = Journal.objects.create(tenant=tenant, currency="USD")
            Posting.objects.create(journal=j, account=accounts[0], amount=10)
            Posting.objects.create(journal=j, account=account, amount=-10)
    original = service.post(user, journal_value(ledger), "first")
    with pytest.raises(IntegrityError), transaction.atomic():
        j = Journal.objects.create(tenant=tenant, currency="USD", reversal_of=original)
        Posting.objects.create(journal=j, account=accounts[0], amount=-1)
        Posting.objects.create(journal=j, account=accounts[1], amount=1)


def test_me05_randomized_reversal_replay(ledger):
    import random

    rng = random.Random(1729)
    user, tenant, accounts = ledger
    expected = {0: 0}
    total = 0
    for i in range(30):
        amount = rng.randint(1, 10000) * (1 if i % 2 else -1)
        j = service.post(user, journal_value(ledger, amount), f"random-{i}")
        total += amount
        expected[j.sequence] = total
        if i % 4 == 0:
            reversal = service.reverse(user, tenant.id, j.id, f"reverse-{i}")
            total -= amount
            expected[reversal.sequence] = total
            assert service.reverse(user, tenant.id, j.id, f"reverse-{i}").id == reversal.id
            with pytest.raises(service.Conflict):
                service.reverse(user, tenant.id, j.id, f"second-{i}")
    for sequence, value in expected.items():
        assert service.balance(user, tenant.id, accounts[0].id, sequence) == value
    Balance.objects.filter(account=accounts[0]).update(amount=999)
    assert not service.audit(user, tenant.id)["consistent"]
    assert service.audit(user, tenant.id, rebuild=True)["rebuilt"]
    assert service.audit(user, tenant.id)["consistent"]


def auth(user, tenant):
    username = get_user_model().objects.get(id=user).username
    return {
        "HTTP_AUTHORIZATION": "Basic "
        + base64.b64encode(f"{username}:synthetic-password".encode()).decode(),
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def test_me06_api_all_endpoints_tenant_isolation(ledger):
    user, tenant, accounts = ledger
    other = Tenant.objects.create(name="private")
    foreign = Account.objects.create(tenant=other, name="secret", currency="USD")
    client = Client()
    headers = auth(user, tenant)
    j = service.post(user, journal_value(ledger), "original")
    assert client.get(f"/api/v1/journals/{j.id}", **headers).status_code == 200
    assert client.get(f"/api/v1/accounts/{foreign.id}/balance", **headers).status_code == 404
    assert client.get(f"/accounts/{foreign.id}", **headers).status_code == 404
    for path in [
        f"/api/v1/journals/{j.id}",
        f"/api/v1/accounts/{accounts[0].id}/balance",
        f"/journals/{j.id}",
        f"/accounts/{accounts[0].id}",
    ]:
        assert client.get(path, **{**headers, "HTTP_X_TENANT_ID": str(other.id)}).status_code == 403
    payload = {
        "currency": "USD",
        "tenant_id": str(tenant.id),
        "postings": [
            {"account_id": str(accounts[0].id), "amount": "1.00"},
            {"account_id": str(foreign.id), "amount": "-1.00"},
        ],
    }
    assert (
        client.post(
            "/api/v1/journals",
            json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="bad",
            **headers,
        ).status_code
        == 400
    )
    for path, body in [
        ("/api/v1/accounts", {"name": "new", "currency": "USD"}),
        (
            "/api/v1/statements/import",
            {"account_id": str(accounts[0].id), "source": "x", "rows": []},
        ),
        ("/api/v1/reconciliation/runs", {"account_id": str(accounts[0].id)}),
        (f"/api/v1/journals/{j.id}/reversal", {}),
    ]:
        assert (
            client.post(
                path,
                json.dumps(body),
                content_type="application/json",
                **{**headers, "HTTP_X_TENANT_ID": str(other.id)},
            ).status_code
            == 403
        )
    assert client.get(f"/api/v1/journals/{j.id}").status_code == 403
    Membership.objects.filter(user_id=user, tenant=tenant).update(verified=False)
    with pytest.raises(service.Forbidden):
        service.balance(user, tenant.id, accounts[0].id)


def test_api_decimal_precision_and_reversal(ledger):
    user, tenant, accounts = ledger
    client = Client()
    headers = auth(user, tenant)
    payload = {
        "currency": "USD",
        "postings": [
            {"account_id": str(accounts[0].id), "amount": "1.00"},
            {"account_id": str(accounts[1].id), "amount": "-1.00"},
        ],
    }
    result = client.post(
        "/api/v1/journals",
        json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api",
        **headers,
    )
    assert result.status_code == 201, result.content
    identity = result.json()["id"]
    response = client.post(
        f"/api/v1/journals/{identity}/reversal",
        "{}",
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reverse",
        **headers,
    )
    assert response.status_code == 201, response.content
    payload["postings"][0]["amount"] = "1.001"
    assert (
        client.post(
            "/api/v1/journals",
            json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="precision",
            **headers,
        ).status_code
        == 400
    )


def make_statements(ledger):
    user, tenant, accounts = ledger
    j = service.post(user, journal_value(ledger), "matchable")
    rows = [
        {
            "id": "row-1",
            "amount": "1.00",
            "currency": "USD",
            "timestamp": j.created_at.isoformat(),
            "reference": "INV100",
        }
    ]
    return reconcile.import_rows(user, tenant.id, accounts[0].id, "bank-2026", rows), rows


def test_me07_reimport_ambiguity_and_concurrent_cross_run_approval(ledger):
    user, tenant, accounts = ledger
    identities, rows = make_statements(ledger)
    assert reconcile.import_rows(user, tenant.id, accounts[0].id, "bank-2026", rows) == identities
    with pytest.raises(service.Conflict):
        reconcile.import_rows(
            user, tenant.id, accounts[0].id, "bank-2026", [{**rows[0], "amount": "2.00"}]
        )
    assert StatementRow.objects.count() == 1
    runs = [reconcile.run(user, tenant.id, accounts[0].id) for _ in range(2)]
    proposals = [r.proposals.get() for r in runs]

    def approve(p):
        try:
            reconcile.decide(user, tenant.id, p.id, "approve")
            return "approved"
        except service.Conflict:
            return "conflict"

    assert sorted(parallel(approve, proposals)) == ["approved", "conflict"]
    assert ApprovedMatch.objects.count() == 1
    assert reconcile.run(user, tenant.id, accounts[0].id).proposals.count() == 0
    with pytest.raises(service.Conflict):
        reconcile.decide(user, tenant.id, ApprovedMatch.objects.get().proposal_id, "reject")


def test_me07_two_rows_one_posting_and_authorization(ledger):
    user, tenant, accounts = ledger
    _, rows = make_statements(ledger)
    reconcile.import_rows(
        user, tenant.id, accounts[0].id, "bank-2026", [{**rows[0], "id": "row-2"}]
    )
    runs = [reconcile.run(user, tenant.id, accounts[0].id) for _ in range(2)]
    assert runs[0].proposals.get().ambiguous
    foreign = Tenant.objects.create(name="foreign")
    with pytest.raises(service.Forbidden):
        reconcile.decide(user, foreign.id, runs[0].proposals.get().id, "approve")
    headers = auth(user, tenant)
    client = Client()
    run = runs[0]
    assert client.get(f"/api/v1/reconciliation/runs/{run.id}?limit=1", **headers).status_code == 200
    assert (
        client.get(f"/api/v1/reconciliation/runs/{run.id}?limit=101", **headers).status_code == 400
    )
    assert (
        client.get(
            f"/api/v1/reconciliation/runs/{run.id}",
            **{**headers, "HTTP_X_TENANT_ID": str(foreign.id)},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/reconciliation/proposals/{run.proposals.get().id}/decision",
            json.dumps({"decision": "approve"}),
            content_type="application/json",
            **headers,
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("0001-01-01T00:00:00+01:00", 400),
        ("9999-12-31T23:59:59-01:00", 400),
        ("0001-01-01T00:00:00Z", 201),
        ("9999-12-31T23:59:59Z", 201),
    ],
)
def test_api_statement_date_boundaries_do_not_cause_server_errors(ledger, timestamp, expected):
    user, tenant, accounts = ledger
    client = Client()
    headers = auth(user, tenant)
    response = client.post(
        "/api/v1/statements/import",
        json.dumps(
            {
                "account_id": str(accounts[0].id),
                "source": "boundary-test",
                "rows": [
                    {
                        "id": "boundary-row",
                        "amount": "1.00",
                        "currency": "USD",
                        "timestamp": timestamp,
                        "reference": "",
                    }
                ],
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == expected, response.content
    assert StatementRow.objects.count() == int(expected == 201)
    if expected == 201:
        response = client.post(
            "/api/v1/reconciliation/runs",
            json.dumps({"account_id": str(accounts[0].id)}),
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 201, response.content
        assert response.json()["summary"]["rows"] == 1


def test_failed_native_restore_rolls_back_schema_and_missing_input_creates_no_database(tmp_path):
    import secrets
    import subprocess

    import psycopg
    from psycopg import sql

    from pp_meridian.persistence.snapshot import _connection_parameters, backup, restore

    target = "meridian_restore_" + secrets.token_hex(8)
    missing_target = "meridian_restore_" + secrets.token_hex(8)
    path = tmp_path / "truncated-data.dump"
    # Keep the archive header/TOC intact and truncate the final incompressible data
    # block, so restoring fails after schema creation and requires a rollback.
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE meridian_restore_test_table(value bytea)")
        cursor.execute(
            "INSERT INTO meridian_restore_test_table VALUES (%s)", [secrets.token_bytes(65536)]
        )
    try:
        backup(path)
        archive = path.read_bytes()
        assert len(archive) > 65536
        path.write_bytes(archive[:-4096])
        with pytest.raises(subprocess.CalledProcessError):
            restore(path, target)
        with psycopg.connect(**_connection_parameters(target)) as restored:
            assert restored.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
            ).fetchone() == (0,)
        with pytest.raises(FileNotFoundError):
            restore(tmp_path / "missing.dump", missing_target)
        with psycopg.connect(**_connection_parameters("postgres"), autocommit=True) as admin:
            assert admin.execute(
                "SELECT count(*) FROM pg_database WHERE datname=%s", [missing_target]
            ).fetchone() == (0,)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE meridian_restore_test_table")
        with psycopg.connect(**_connection_parameters("postgres"), autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target))
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(missing_target)
                )
            )


def test_native_client_environment_connects_with_configured_libpq_options(monkeypatch):
    import subprocess
    import sys
    from types import SimpleNamespace

    from django.conf import settings

    from pp_meridian.persistence import snapshot

    config = dict(settings.DATABASES["default"])
    config["OPTIONS"] = {**config.get("OPTIONS", {}), "options": "-c statement_timeout=1234"}
    monkeypatch.setattr(snapshot, "settings", SimpleNamespace(DATABASES={"default": config}))
    monkeypatch.delenv("MERIDIAN_PG_CONTAINER", raising=False)
    monkeypatch.setattr(snapshot.shutil, "which", lambda _: sys.executable)
    with snapshot._command("pg_dump", config["NAME"]) as (_, environment):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, psycopg; "
                "connection = psycopg.connect(); "
                'print(json.dumps(connection.execute("SELECT current_database(), '
                "current_setting('statement_timeout')\").fetchone())); connection.close()",
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    assert json.loads(result.stdout) == [config["NAME"], "1234ms"]


def test_me03_retry_whole_aborted_transaction_real_sqlstate(ledger):
    user, tenant, accounts = ledger
    attempts = []

    def operation():
        attempts.append(len(attempts))
        Account.objects.create(tenant=tenant, name="rolled-back-on-retry", currency="USD")
        if len(attempts) == 1:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DO $$ BEGIN RAISE EXCEPTION 'forced serialization conflict' USING ERRCODE='40001'; END $$"
                )
        return len(attempts)

    before = service.retry_count()
    assert service.retry_transaction(operation) == 2
    assert Account.objects.filter(name="rolled-back-on-retry").count() == 1
    assert service.retry_count() == before + 1
    with pytest.raises(RuntimeError):
        service.retry_transaction(lambda: (_ for _ in ()).throw(RuntimeError("not retryable")))


def test_me04_nonowner_database_role_still_enforces_constraints(ledger):
    user, tenant, accounts = ledger
    journal = service.post(user, journal_value(ledger), "role")
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user")
        can_create = cursor.fetchone()[0]
    # CI's service role and local service role both own their test database.
    # A preconfigured restricted role can be supplied where CREATE ROLE is disallowed.
    import os

    role = os.environ.get("MERIDIAN_TEST_RESTRICTED_ROLE", "meridian_constraint_test")
    from psycopg import sql

    with connection.cursor() as cursor:
        if can_create:
            cursor.execute(
                sql.SQL(
                    "DO $$ BEGIN IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname={}) THEN CREATE ROLE {} NOLOGIN NOSUPERUSER; END IF; END $$"
                ).format(sql.Literal(role), sql.Identifier(role))
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(sql.Identifier(role))
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                    sql.Identifier(role)
                )
            )
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            cursor.execute(
                "UPDATE meridian_journal SET reference='tamper' WHERE id=%s", [journal.id]
            )


def test_me08_migration_from_previous_fixture_schema():
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("meridian", "0001_initial")])
    state = executor.loader.project_state([("meridian", "0001_initial")]).apps
    T = state.get_model("meridian", "Tenant")
    A = state.get_model("meridian", "Account")
    J = state.get_model("meridian", "Journal")
    P = state.get_model("meridian", "Posting")
    t = T.objects.create(name="previous schema fixture", last_sequence=1)
    a = A.objects.create(tenant=t, name="bank", currency="USD")
    b = A.objects.create(tenant=t, name="offset", currency="USD")
    j = J.objects.create(tenant=t, currency="USD", sequence=1)
    P.objects.create(journal=j, account=a, amount=100)
    P.objects.create(journal=j, account=b, amount=-100)
    executor = MigrationExecutor(connection)
    executor.migrate([("meridian", "0005_tenant_identity_history")])
    assert Journal.objects.get(id=j.id).sequence == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        Journal.objects.filter(id=j.id).update(currency="CAD")


def test_me08_native_snapshot_restore(ledger, tmp_path):
    import secrets

    import psycopg
    from django.conf import settings
    from psycopg import sql

    from pp_meridian.persistence.snapshot import backup, restore

    user, tenant, accounts = ledger
    j = service.post(user, journal_value(ledger), "backup")
    target = "meridian_restore_" + secrets.token_hex(8)
    path = tmp_path / "snapshot.dump"
    backup(path)
    assert path.stat().st_size > 0
    config = settings.DATABASES["default"]
    kwargs = {
        "host": config["HOST"],
        "port": config["PORT"],
        "user": config["USER"],
        "password": config["PASSWORD"],
    }
    try:
        restore(path, target)
        with psycopg.connect(**kwargs, dbname=target) as restored:
            assert (
                restored.execute(
                    "SELECT count(*) FROM meridian_journal WHERE id=%s", [j.id]
                ).fetchone()[0]
                == 1
            )
            rows = restored.execute(
                "SELECT p.account_id,sum(p.amount) FROM meridian_posting p GROUP BY p.account_id"
            ).fetchall()
            assert dict(rows)[accounts[0].id] == 100
            with pytest.raises(psycopg.errors.CheckViolation):
                with restored.transaction():
                    restored.execute("UPDATE meridian_posting SET amount=0")
    finally:
        with psycopg.connect(**kwargs, dbname="postgres", autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target))
            )


def test_me04_killed_process_rolls_back_unacknowledged_posting(ledger):
    import os
    import subprocess
    import sys
    from urllib.parse import quote

    from django.conf import settings

    user, tenant, accounts = ledger
    config = settings.DATABASES["default"]
    url = f"postgresql://{quote(str(config['USER']))}:{quote(str(config['PASSWORD']))}@{config['HOST']}:{config['PORT']}/{config['NAME']}"
    code = """import os,django
from uuid import UUID
os.environ.setdefault("DJANGO_SETTINGS_MODULE","pp_meridian.config.settings")
django.setup()
from pp_meridian.application.ledger import post
from pp_meridian.domain.journal import Entry,JournalValue
post(int(os.environ["TEST_USER"]),JournalValue(UUID(os.environ["TEST_TENANT"]),"USD",(Entry(UUID(os.environ["TEST_ACCOUNT_A"]),100),Entry(UUID(os.environ["TEST_ACCOUNT_B"]),-100))),"killed",fault=lambda:os._exit(91))
"""
    env = {
        **os.environ,
        "MERIDIAN_DATABASE_URL": url,
        "TEST_USER": str(user),
        "TEST_TENANT": str(tenant.id),
        "TEST_ACCOUNT_A": str(accounts[0].id),
        "TEST_ACCOUNT_B": str(accounts[1].id),
    }
    child = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 91, child.stderr.decode()
    assert Journal.objects.count() == Posting.objects.count() == Idempotency.objects.count() == 0
    assert all(amount == 0 for amount in Balance.objects.values_list("amount", flat=True))


def test_me05_sequence_lock_held_until_commit(ledger):
    from threading import Event

    user, tenant, accounts = ledger
    first_waiting, release, second_started = Event(), Event(), Event()

    def hold():
        first_waiting.set()
        if not release.wait(timeout=10):
            raise RuntimeError("test release deadline")

    def first():
        close_old_connections()
        try:
            return service.post(user, journal_value(ledger), "held", fault=hold)
        finally:
            close_old_connections()

    def second():
        close_old_connections()
        second_started.set()
        try:
            return service.post(user, journal_value(ledger), "follower")
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert first_waiting.wait(timeout=10)
        b = pool.submit(second)
        assert second_started.wait(timeout=10)
        try:
            assert service.balance(user, tenant.id, accounts[0].id, 1) == 0
            assert not b.done()
        finally:
            release.set()
        assert (a.result().sequence, b.result().sequence) == (1, 2)
    assert service.balance(user, tenant.id, accounts[0].id, 1) == 100


def test_projection_missing_requires_rebuild_and_transaction_ownership(ledger):
    user, tenant, accounts = ledger
    Balance.objects.filter(account=accounts[0]).delete()
    with pytest.raises(service.Conflict):
        service.post(user, journal_value(ledger), "missing-projection")
    assert Journal.objects.count() == 0
    assert not service.audit(user, tenant.id)["consistent"]
    service.audit(user, tenant.id, rebuild=True)
    assert service.audit(user, tenant.id)["consistent"]
    with transaction.atomic(), pytest.raises(RuntimeError, match="outer transaction"):
        service.post(user, journal_value(ledger), "outer")


def test_me06_database_idempotency_tenant_journal_binding(ledger):
    user, tenant, accounts = ledger
    other = Tenant.objects.create(name="private idempotency tenant")
    foreign_accounts = [
        Account.objects.create(tenant=other, name=f"private-{i}", currency="USD") for i in range(2)
    ]
    with transaction.atomic():
        foreign = Journal.objects.create(tenant=other, currency="USD")
        Posting.objects.create(journal=foreign, account=foreign_accounts[0], amount=100)
        Posting.objects.create(journal=foreign, account=foreign_accounts[1], amount=-100)
    assert not Membership.objects.filter(user_id=user, tenant=other).exists()
    value = journal_value(ledger)
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO meridian_idempotency (tenant_id,key,payload_hash,journal_id) VALUES (%s,%s,%s,%s)",
                [tenant.id, "poisoned", service.payload_hash(value), foreign.id],
            )
    posted = service.post(user, value, "poisoned")
    assert posted.tenant_id == tenant.id and posted.id != foreign.id
    assert all(p.account.tenant_id == tenant.id for p in posted.postings.select_related("account"))
    with pytest.raises(service.Forbidden):
        service.history(user, other.id)


def test_me06_legacy_poisoned_cache_defense_and_upgrade_validation(ledger):
    from django.db.migrations.executor import MigrationExecutor

    user, tenant, accounts = ledger
    executor = MigrationExecutor(connection)
    executor.migrate([("meridian", "0004_account_insert_lock")])
    try:
        other = Tenant.objects.create(name="legacy private tenant")
        aa = [
            Account.objects.create(tenant=other, name=f"private-{i}", currency="USD")
            for i in range(2)
        ]
        with transaction.atomic():
            foreign = Journal.objects.create(tenant=other, currency="USD")
            Posting.objects.create(journal=foreign, account=aa[0], amount=100)
            Posting.objects.create(journal=foreign, account=aa[1], amount=-100)
            Idempotency.objects.create(
                tenant=tenant,
                key="legacy-poison",
                payload_hash=service.payload_hash(journal_value(ledger)),
                journal=foreign,
            )
        with pytest.raises(service.Conflict, match="journal tenant mismatch"):
            service.post(user, journal_value(ledger), "legacy-poison")
        assert not Membership.objects.filter(user_id=user, tenant=other).exists()
        # Upgrades validate existing cache rows; corruption is not grandfathered in.
        with pytest.raises(IntegrityError):
            MigrationExecutor(connection).migrate([("meridian", "0005_tenant_identity_history")])
    finally:
        # Administrative repair applies only to this isolated previous-schema test fixture.
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE meridian_idempotency")
        MigrationExecutor(connection).migrate([("meridian", "0005_tenant_identity_history")])


def test_me06_statement_and_empty_run_freeze_account_identity(ledger):
    from pp_meridian.persistence.models import ReconciliationRun

    user, tenant, accounts = ledger
    other = Tenant.objects.create(name="foreign identity target")
    reconcile.import_rows(
        user,
        tenant.id,
        accounts[0].id,
        "identity-statement",
        [
            {
                "id": "row",
                "amount": "1.00",
                "currency": "USD",
                "timestamp": "2026-10-17T12:00:00Z",
                "reference": "rent",
            }
        ],
    )
    result = reconcile.run(user, tenant.id, accounts[1].id)
    assert result.proposals.count() == 0
    for account in accounts[:2]:
        for values in [{"currency": "CAD"}, {"tenant_id": other.id}]:
            with pytest.raises(IntegrityError), transaction.atomic():
                Account.objects.filter(id=account.id).update(**values)
    with pytest.raises(IntegrityError), transaction.atomic():
        ReconciliationRun.objects.filter(id=result.id).update(account_id=accounts[2].id)
    assert StatementRow.objects.get().account.tenant_id == tenant.id
    assert StatementRow.objects.get().account.currency == "USD"


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("change", ["currency", "tenant"])
def test_me06_concurrent_statement_import_then_account_change(ledger, direct, change):
    from datetime import datetime, timezone
    from threading import Event

    user, tenant, accounts = ledger
    account = accounts[2]
    other = Tenant.objects.create(name="racing identity target")
    imported, release, mutating = Event(), Event(), Event()

    def importer():
        close_old_connections()
        try:
            with transaction.atomic():
                if direct:
                    StatementRow.objects.create(
                        account=account,
                        source="direct-race",
                        identity="row",
                        payload_hash="0" * 64,
                        amount=100,
                        currency="USD",
                        timestamp=datetime.now(timezone.utc),
                        reference="rent",
                    )
                else:
                    reconcile.import_rows(
                        user,
                        tenant.id,
                        account.id,
                        "application-race",
                        [
                            {
                                "id": "row",
                                "amount": "1.00",
                                "currency": "USD",
                                "timestamp": "2026-10-17T12:00:00Z",
                                "reference": "rent",
                            }
                        ],
                    )
                imported.set()
                if not release.wait(10):
                    raise RuntimeError("import release deadline")
        finally:
            close_old_connections()

    def mutate():
        close_old_connections()
        mutating.set()
        try:
            try:
                Account.objects.filter(id=account.id).update(
                    **({"currency": "CAD"} if change == "currency" else {"tenant_id": other.id})
                )
                return "changed"
            except IntegrityError:
                return "rejected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(importer)
        assert imported.wait(10)
        b = pool.submit(mutate)
        assert mutating.wait(10)
        try:
            assert not b.done()
        finally:
            release.set()
        a.result()
        assert b.result() == "rejected"
    account.refresh_from_db()
    assert (account.tenant_id, account.currency) == (tenant.id, "USD")


def test_me07_proposal_identity_cannot_move_after_publication(ledger):
    user, tenant, accounts = ledger
    make_statements(ledger)
    runs = [reconcile.run(user, tenant.id, accounts[0].id) for _ in range(2)]
    proposal = runs[0].proposals.get()
    for values in [{"run_id": runs[1].id}, {"ambiguous": not proposal.ambiguous}]:
        with pytest.raises(IntegrityError), transaction.atomic():
            Proposal.objects.filter(id=proposal.id).update(**values)


def test_me06_upgrade_rejects_legacy_statement_currency_inconsistency(ledger):
    from django.db.migrations.executor import MigrationExecutor

    user, tenant, accounts = ledger
    MigrationExecutor(connection).migrate([("meridian", "0004_account_insert_lock")])
    try:
        reconcile.import_rows(
            user,
            tenant.id,
            accounts[2].id,
            "legacy-currency",
            [
                {
                    "id": "row",
                    "amount": "1.00",
                    "currency": "USD",
                    "timestamp": "2026-10-17T12:00:00Z",
                    "reference": "rent",
                }
            ],
        )
        Account.objects.filter(id=accounts[2].id).update(currency="CAD")
        with pytest.raises(IntegrityError, match="history violates account identity"):
            MigrationExecutor(connection).migrate([("meridian", "0005_tenant_identity_history")])
    finally:
        Account.objects.filter(id=accounts[2].id).update(currency="USD")
        MigrationExecutor(connection).migrate([("meridian", "0005_tenant_identity_history")])
