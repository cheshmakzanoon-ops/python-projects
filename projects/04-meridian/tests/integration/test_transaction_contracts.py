"""Database and concurrency contracts beyond ordinary API validation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction

from pp_meridian.application import ledger as service
from pp_meridian.application import reconcile
from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.persistence.models import (
    ApprovedMatch,
    Balance,
    DecisionAudit,
    Idempotency,
    Journal,
    Membership,
    Posting,
    Proposal,
    ReconciliationRun,
    StatementRow,
    Tenant,
)

pytestmark = pytest.mark.django_db(transaction=True)


def journal_value(ledger, amount=100):
    _, tenant, accounts = ledger
    return JournalValue(
        tenant.id,
        "USD",
        (Entry(accounts[0].id, amount), Entry(accounts[1].id, -amount)),
        "INV-CORE",
    )


def proposal(ledger):
    user, tenant, accounts = ledger
    journal = service.post(user, journal_value(ledger), "match-source")
    reconcile.import_rows(
        user,
        tenant.id,
        accounts[0].id,
        "bank-core",
        [
            {
                "id": "row",
                "amount": "1.00",
                "currency": "USD",
                "timestamp": journal.created_at.isoformat(),
                "reference": "INVCORE",
            }
        ],
    )
    return reconcile.run(user, tenant.id, accounts[0].id).proposals.get()


def test_journal_created_in_savepoint_accepts_its_own_transaction_postings(ledger):
    _, tenant, accounts = ledger
    with transaction.atomic():
        with transaction.atomic():
            journal = Journal.objects.create(tenant=tenant, currency="USD")
        Posting.objects.bulk_create(
            [
                Posting(journal=journal, account=accounts[0], amount=100),
                Posting(journal=journal, account=accounts[1], amount=-100),
            ]
        )
    assert journal.postings.count() == 2
    with pytest.raises(IntegrityError), transaction.atomic():
        Posting.objects.create(journal=journal, account=accounts[2], amount=1)


def test_committed_journal_seal_cannot_be_reopened(ledger):
    user, _, _ = ledger
    journal = service.post(user, journal_value(ledger), "sealed")
    with connection.cursor() as cursor:
        cursor.execute("SELECT sealed FROM meridian_journal WHERE id=%s", [journal.id])
        assert cursor.fetchone() == (True,)
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("UPDATE meridian_journal SET sealed=false WHERE id=%s", [journal.id])


def test_manually_sealing_an_incomplete_journal_does_not_skip_balance_validation(ledger):
    _, tenant, _ = ledger
    with pytest.raises(IntegrityError, match="balanced"), transaction.atomic():
        journal = Journal.objects.create(tenant=tenant, currency="USD")
        with connection.cursor() as cursor:
            cursor.execute("UPDATE meridian_journal SET sealed=true WHERE id=%s", [journal.id])
    assert Journal.objects.count() == 0


def test_idempotency_hash_must_describe_the_actual_immutable_journal(ledger):
    user, tenant, accounts = ledger
    with transaction.atomic():
        journal = Journal.objects.create(tenant=tenant, currency="USD", reference="INV-CORE")
        Posting.objects.bulk_create(
            [
                Posting(journal=journal, account=accounts[0], amount=100),
                Posting(journal=journal, account=accounts[1], amount=-100),
            ]
        )
        Idempotency.objects.create(
            tenant=tenant,
            key="corrupt-same-tenant-cache",
            journal=journal,
            payload_hash=service.payload_hash(journal_value(ledger, 200)),
        )
    with pytest.raises(service.Conflict, match="journal"):
        service.post(user, journal_value(ledger, 200), "corrupt-same-tenant-cache")
    assert Journal.objects.count() == 1


@pytest.mark.parametrize("incomplete", ["status", "match", "audit"])
def test_approval_status_cannot_commit_without_match_and_audit(ledger, incomplete):
    target = proposal(ledger)
    with pytest.raises(IntegrityError), transaction.atomic():
        if incomplete == "status":
            Proposal.objects.filter(id=target.id).update(status="approved")
        elif incomplete == "match":
            ApprovedMatch.objects.create(
                proposal=target, row_id=target.row_id, posting_id=target.posting_id
            )
        else:
            DecisionAudit.objects.create(proposal=target, user_id=ledger[0], decision="approve")
    target.refresh_from_db()
    assert target.status == "pending"


def test_rejected_proposal_cannot_be_reopened_by_direct_sql(ledger):
    user, tenant, _ = ledger
    target = proposal(ledger)
    reconcile.decide(user, tenant.id, target.id, "reject")
    with pytest.raises(IntegrityError), transaction.atomic():
        Proposal.objects.filter(id=target.id).update(status="pending")
    target.refresh_from_db()
    assert target.status == "rejected"


def test_published_proposal_cannot_be_deleted(ledger):
    target = proposal(ledger)
    with pytest.raises(IntegrityError), transaction.atomic():
        Proposal.objects.filter(id=target.id).delete()


def test_published_proposal_primary_key_cannot_change(ledger):
    target = proposal(ledger)
    with pytest.raises(IntegrityError), transaction.atomic():
        Proposal.objects.filter(id=target.id).update(id=uuid4())


def test_tenant_counter_cannot_be_rewritten_outside_journal_allocation(ledger):
    user, tenant, _ = ledger
    journal = service.post(user, journal_value(ledger), "counter")
    with pytest.raises(IntegrityError), transaction.atomic():
        Tenant.objects.filter(id=tenant.id).update(last_sequence=journal.sequence + 100)
    tenant.refresh_from_db()
    assert tenant.last_sequence == journal.sequence


def create_balanced_journal(tenant, accounts):
    journal = Journal.objects.create(tenant=tenant, currency="USD")
    Posting.objects.bulk_create(
        [
            Posting(journal=journal, account=accounts[0], amount=100),
            Posting(journal=journal, account=accounts[1], amount=-100),
        ]
    )
    return journal


def ignore_existing_journal(journal):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO meridian_journal(id,tenant_id,currency,sequence,reference,created_at) "
            "VALUES(%s,%s,%s,0,'ignored',now()) ON CONFLICT DO NOTHING",
            [journal.id, journal.tenant_id, journal.currency],
        )


@pytest.mark.parametrize("then_insert", [False, True])
def test_ignored_journal_insert_cannot_consume_a_committed_sequence(ledger, then_insert):
    user, tenant, accounts = ledger
    first = service.post(user, journal_value(ledger), "before-conflict")
    with pytest.raises(IntegrityError, match="counter"), transaction.atomic():
        ignore_existing_journal(first)
        if then_insert:
            create_balanced_journal(tenant, accounts)
    tenant.refresh_from_db()
    assert tenant.last_sequence == first.sequence == 1
    assert list(Journal.objects.filter(tenant=tenant).values_list("sequence", flat=True)) == [1]
    assert service.post(user, journal_value(ledger), "after-conflict").sequence == 2


def test_bulk_ignored_conflicts_cannot_hide_sequence_gaps(ledger):
    user, tenant, _ = ledger
    existing = service.post(user, journal_value(ledger), "bulk-existing")
    with pytest.raises(IntegrityError, match="counter"), transaction.atomic():
        Journal.objects.bulk_create(
            [
                Journal(id=existing.id, tenant=tenant, currency="USD"),
                Journal(id=existing.id, tenant=tenant, currency="USD"),
            ],
            ignore_conflicts=True,
        )
    tenant.refresh_from_db()
    assert tenant.last_sequence == 1
    assert Journal.objects.filter(tenant=tenant).count() == 1


def test_deferred_sequence_checks_use_final_state_and_respect_savepoint_rollback(ledger):
    _, tenant, accounts = ledger
    with transaction.atomic():
        first = create_balanced_journal(tenant, accounts)
        with transaction.atomic():
            ignore_existing_journal(first)
            transaction.set_rollback(True)
        second = create_balanced_journal(tenant, accounts)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    tenant.refresh_from_db()
    assert tenant.last_sequence == 2
    assert list(
        Journal.objects.filter(tenant=tenant)
        .order_by("sequence")
        .values_list("sequence", flat=True)
    ) == [1, 2]
    assert first.id != second.id


def test_new_tenant_can_allocate_multiple_journals_before_first_commit(ledger):
    user, _, _ = ledger
    with transaction.atomic():
        tenant = Tenant.objects.create(name="Created inside transaction")
        Membership.objects.create(user_id=user, tenant=tenant, verified=True)
        accounts = [service.create_account(user, tenant.id, str(n), "USD") for n in range(2)]
        create_balanced_journal(tenant, accounts)
        create_balanced_journal(tenant, accounts)
    tenant.refresh_from_db()
    assert tenant.last_sequence == 2


def test_upgrade_rejects_legacy_gap_even_when_counter_matches_maximum(ledger):
    from django.db.migrations.executor import MigrationExecutor

    user, tenant, accounts = ledger
    first = service.post(user, journal_value(ledger), "legacy-first")
    MigrationExecutor(connection).migrate([("meridian", "0005_tenant_identity_history")])
    try:
        with transaction.atomic():
            ignore_existing_journal(first)
            create_balanced_journal(tenant, accounts)
            tenant.refresh_from_db()
            assert tenant.last_sequence == 3
            assert list(
                Journal.objects.filter(tenant=tenant)
                .order_by("sequence")
                .values_list("sequence", flat=True)
            ) == [1, 3]
            # Flush valid accounting/FK events before schema alteration, while
            # retaining the outer rollback that leaves this shared test DB clean.
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with pytest.raises(IntegrityError, match="counter"), transaction.atomic():
                MigrationExecutor(connection).migrate([("meridian", "0006_transaction_contracts")])
            transaction.set_rollback(True)
    finally:
        MigrationExecutor(connection).migrate([("meridian", "0006_transaction_contracts")])
    tenant.refresh_from_db()
    assert tenant.last_sequence == 1


@pytest.mark.parametrize("revocation", ["membership", "user"])
def test_membership_revocation_waits_until_authorized_post_finishes(ledger, revocation):
    user, tenant, _ = ledger
    posted, release, revoked = Event(), Event(), Event()

    def pause_before_commit():
        posted.set()
        if not release.wait(10):
            raise RuntimeError("release deadline")

    def post():
        close_old_connections()
        try:
            return service.post(user, journal_value(ledger), "auth-lock", fault=pause_before_commit)
        finally:
            close_old_connections()

    def revoke():
        close_old_connections()
        try:
            if revocation == "membership":
                Membership.objects.filter(user_id=user, tenant=tenant).update(verified=False)
            else:
                get_user_model().objects.filter(id=user).update(is_active=False)
            revoked.set()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        posting = executor.submit(post)
        assert posted.wait(10)
        revoking = executor.submit(revoke)
        try:
            assert not revoked.wait(0.3), "revocation committed before the authorized posting"
        finally:
            release.set()
        posting.result(timeout=10)
        revoking.result(timeout=10)
    assert revoked.is_set()
    with pytest.raises(service.Forbidden):
        service.post(user, journal_value(ledger), "after-revocation")


def test_same_principal_can_post_to_independent_tenants_concurrently(ledger):
    user, _, _ = ledger
    other = Tenant.objects.create(name="Independent tenant")
    Membership.objects.create(user_id=user, tenant=other, verified=True)
    accounts = [service.create_account(user, other.id, str(i), "USD") for i in range(2)]
    independent = JournalValue(
        other.id, "USD", (Entry(accounts[0].id, 25), Entry(accounts[1].id, -25))
    )
    held, release = Event(), Event()

    def pause():
        held.set()
        if not release.wait(10):
            raise RuntimeError("release deadline")

    def post(value, key, fault=None):
        close_old_connections()
        try:
            return service.post(user, value, key, fault=fault)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(post, journal_value(ledger), "held", pause)
        assert held.wait(10)
        try:
            second = executor.submit(post, independent, "independent")
            assert second.result(timeout=3).sequence == 1
        finally:
            release.set()
        assert first.result(timeout=10).sequence == 1


def test_rebuild_serializes_with_posting_without_losing_an_increment(ledger, monkeypatch):
    user, tenant, accounts = ledger
    service.post(user, journal_value(ledger), "before-rebuild")
    Balance.objects.filter(account=accounts[0]).update(amount=999)
    Balance.objects.filter(account=accounts[1]).delete()
    monkeypatch.setattr(service, "REBUILD_BATCH_SIZE", 2)
    rebuilding, release, posted = Event(), Event(), Event()
    real_replay = service.replay

    def pause_after_replay(rows, as_of=None):
        result = real_replay(rows, as_of)
        rebuilding.set()
        if not release.wait(10):
            raise RuntimeError("rebuild release deadline")
        return result

    monkeypatch.setattr(service, "replay", pause_after_replay)

    def rebuild():
        close_old_connections()
        try:
            return service.audit(user, tenant.id, rebuild=True)
        finally:
            close_old_connections()

    def post():
        close_old_connections()
        try:
            result = service.post(user, journal_value(ledger, 50), "after-rebuild")
            posted.set()
            return result
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        repairing = executor.submit(rebuild)
        assert rebuilding.wait(10)
        posting = executor.submit(post)
        try:
            assert not posted.wait(0.2)
        finally:
            release.set()
        assert repairing.result(timeout=10)["rebuilt"]
        assert posting.result(timeout=10).sequence == 2
    monkeypatch.setattr(service, "replay", real_replay)
    assert service.audit(user, tenant.id)["consistent"]
    assert list(
        Balance.objects.filter(account__in=accounts[:2])
        .order_by("amount")
        .values_list("amount", flat=True)
    ) == [-150, 150]
    assert service.balance(user, tenant.id, accounts[0].id, 1) == 100


@pytest.mark.parametrize("corruption", ["counter", "decision"])
def test_upgrade_refuses_inconsistent_legacy_state(ledger, corruption):
    from django.db.migrations.executor import MigrationExecutor

    user, tenant, _ = ledger
    target = proposal(ledger)
    MigrationExecutor(service.connection).migrate([("meridian", "0005_tenant_identity_history")])
    original_counter = Tenant.objects.get(id=tenant.id).last_sequence
    try:
        if corruption == "counter":
            Tenant.objects.filter(id=tenant.id).update(last_sequence=original_counter + 100)
        else:
            Proposal.objects.filter(id=target.id).update(status="approved")
        with pytest.raises(IntegrityError):
            MigrationExecutor(service.connection).migrate(
                [("meridian", "0006_transaction_contracts")]
            )
    finally:
        Tenant.objects.filter(id=tenant.id).update(last_sequence=original_counter)
        Proposal.objects.filter(id=target.id).update(status="pending")
        MigrationExecutor(service.connection).migrate([("meridian", "0006_transaction_contracts")])


def test_large_account_can_use_explicit_statement_batches_without_truncation(ledger, monkeypatch):
    user, tenant, accounts = ledger
    target = proposal(ledger)
    original = StatementRow.objects.get(id=target.row_id)
    another = reconcile.import_rows(
        user,
        tenant.id,
        accounts[0].id,
        "next-bank-batch",
        [
            {
                "id": "another",
                "amount": "1.00",
                "currency": "USD",
                "timestamp": original.timestamp.isoformat(),
                "reference": "INVCORE",
            }
        ],
    )[0]
    monkeypatch.setattr(reconcile, "MAX_RUN_ROWS", 1)
    before = ReconciliationRun.objects.count()
    with pytest.raises(ValueError, match="row_ids batch"):
        reconcile.run(user, tenant.id, accounts[0].id)
    assert ReconciliationRun.objects.count() == before
    selected = reconcile.run(user, tenant.id, accounts[0].id, [another])
    assert selected.summary["rows"] == 1
    assert selected.summary["selected_row_ids"] == [str(another)]
    assert selected.proposals.get().row_id == another
    with pytest.raises(ValueError, match="unmatched rows"):
        reconcile.run(user, tenant.id, accounts[1].id, [another])
    with pytest.raises(ValueError, match="unique"):
        reconcile.run(user, tenant.id, accounts[0].id, [another, another])


def test_candidate_population_budget_rejects_whole_scope(ledger, monkeypatch):
    user, tenant, accounts = ledger
    proposal(ledger)
    service.post(user, journal_value(ledger), "second-candidate")
    monkeypatch.setattr(reconcile, "MAX_RUN_POSTINGS", 1)
    before = ReconciliationRun.objects.count()
    with pytest.raises(ValueError, match="eligible postings"):
        reconcile.run(user, tenant.id, accounts[0].id)
    assert ReconciliationRun.objects.count() == before
