"""READ COMMITTED, tenant row serialization, ordered account locks, bounded retry.

The tenant lock is held until commit, making sequence numbers a committed prefix.
No database-enforced end-user RLS claim is made: verified membership is checked
inside every application operation. PostgreSQL enforces accounting invariants.
"""

import hashlib
import json
import random
import threading
import time
from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from django.db import OperationalError, connection, transaction

from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.domain.money import EXPONENTS
from pp_meridian.domain.replay import HistoricalPosting, replay
from pp_meridian.persistence.models import (
    Account,
    Balance,
    Idempotency,
    Journal,
    Membership,
    Posting,
    Tenant,
)

T = TypeVar("T")
_retry_lock = threading.Lock()
_retry_count = 0


def retry_count() -> int:
    with _retry_lock:
        return _retry_count


class Forbidden(PermissionError):
    pass


class Conflict(ValueError):
    pass


def authorize(user_id: int, tenant_id: UUID) -> None:
    if not Membership.objects.filter(
        user_id=user_id, tenant_id=tenant_id, verified=True, user__is_active=True
    ).exists():
        raise Forbidden("verified tenant membership required")


def retry_transaction(operation: Callable[[], T], retries: int = 4) -> T:
    global _retry_count
    if connection.in_atomic_block:
        raise RuntimeError("ledger operation requires ownership of the outer transaction")
    for attempt in range(retries + 1):
        try:
            with transaction.atomic():
                return operation()
        except OperationalError as error:
            if (
                getattr(error.__cause__, "sqlstate", None) not in {"40001", "40P01"}
                or attempt == retries
            ):
                raise
            with _retry_lock:
                _retry_count += 1
            time.sleep(random.uniform(0.001, 0.005) * (attempt + 1))
    raise AssertionError("unreachable")


def create_account(user_id: int, tenant_id: UUID, name: str, currency: str) -> Account:
    authorize(user_id, tenant_id)
    if (
        currency not in EXPONENTS
        or not isinstance(name, str)
        or not name.strip()
        or len(name) > 150
    ):
        raise ValueError("invalid name/currency")
    with transaction.atomic():
        account = Account.objects.create(tenant_id=tenant_id, name=name, currency=currency)
        Balance.objects.create(account=account)
        return account


def payload_hash(value: JournalValue, reversal_of: UUID | None = None) -> str:
    payload = {
        "tenant": str(value.tenant_id),
        "currency": value.currency,
        "reference": value.reference,
        "postings": sorted([(str(e.account_id), e.amount) for e in value.entries]),
        "reversal_of": str(reversal_of) if reversal_of else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def post(
    user_id: int,
    value: JournalValue,
    key: str,
    reversal_of: UUID | None = None,
    fault: Callable[[], None] | None = None,
) -> Journal:
    value.validate()
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise ValueError("idempotency key required, maximum 200 characters")
    digest = payload_hash(value, reversal_of)

    def execute() -> Journal:
        authorize(user_id, value.tenant_id)
        sequencing_tenant = Tenant.objects.select_for_update().get(id=value.tenant_id)
        existing = (
            Idempotency.objects.filter(tenant_id=value.tenant_id, key=key)
            .select_related("journal")
            .first()
        )
        if existing:
            if existing.journal.tenant_id != value.tenant_id:
                raise Conflict("idempotency journal tenant mismatch")
            if existing.payload_hash != digest:
                raise Conflict("idempotency payload mismatch")
            return existing.journal
        accounts = list(
            Account.objects.select_for_update()
            .filter(id__in=[e.account_id for e in value.entries])
            .order_by("id")
        )
        if len(accounts) != len(value.entries) or any(
            a.tenant_id != value.tenant_id or a.currency != value.currency for a in accounts
        ):
            raise ValueError("account tenant/currency mismatch")
        if reversal_of:
            original = Journal.objects.get(id=reversal_of, tenant_id=value.tenant_id)
            if original.reversal_of_id or Journal.objects.filter(reversal_of=original).exists():
                raise Conflict("only one full reversal is permitted")
        journal = Journal.objects.create(
            tenant_id=value.tenant_id,
            currency=value.currency,
            reference=value.reference,
            reversal_of_id=reversal_of,
        )
        Posting.objects.bulk_create(
            [
                Posting(journal=journal, account_id=e.account_id, amount=e.amount)
                for e in value.entries
            ]
        )
        ordered_entries = sorted(value.entries, key=lambda e: str(e.account_id))
        placeholders = ",".join(["(%s::uuid,%s::bigint)"] * len(ordered_entries))
        parameters: list[UUID | int] = [
            item for entry in ordered_entries for item in (entry.account_id, entry.amount)
        ]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE meridian_balance AS b SET amount=b.amount+v.amount FROM (VALUES "
                + placeholders
                + ") AS v(account_id,amount) WHERE b.account_id=v.account_id RETURNING b.account_id",
                parameters,
            )
            if len(cursor.fetchall()) != len(ordered_entries):
                raise Conflict("missing balance projection; operator replay required")
        if fault:
            fault()
        Idempotency.objects.create(
            tenant_id=value.tenant_id, key=key, payload_hash=digest, journal=journal
        )
        journal.sequence = sequencing_tenant.last_sequence + 1
        return journal

    return retry_transaction(execute)


def reverse(user_id: int, tenant_id: UUID, journal_id: UUID, key: str) -> Journal:
    authorize(user_id, tenant_id)
    journal = Journal.objects.get(id=journal_id, tenant_id=tenant_id)
    value = JournalValue(
        tenant_id,
        journal.currency,
        tuple(Entry(p.account_id, -p.amount) for p in journal.postings.all()),
        journal.reference,
    )
    return post(user_id, value, key, journal_id)


def history(user_id: int, tenant_id: UUID) -> list[HistoricalPosting]:
    authorize(user_id, tenant_id)
    return [
        HistoricalPosting(account, currency, amount, sequence)
        for account, currency, amount, sequence in Posting.objects.filter(
            journal__tenant_id=tenant_id
        )
        .values_list("account_id", "journal__currency", "amount", "journal__sequence")
        .order_by("journal__sequence", "id")
    ]


def balance(user_id: int, tenant_id: UUID, account_id: UUID, as_of: int | None = None) -> int:
    authorize(user_id, tenant_id)
    Account.objects.get(id=account_id, tenant_id=tenant_id)
    if as_of is not None and as_of < 0:
        raise ValueError("sequence must be nonnegative")
    return replay(history(user_id, tenant_id), as_of).get(account_id, 0)


def audit(user_id: int, tenant_id: UUID, rebuild: bool = False) -> dict[str, object]:
    def execute() -> dict[str, object]:
        authorize(user_id, tenant_id)
        Tenant.objects.select_for_update().get(id=tenant_id)
        expected = replay(history(user_id, tenant_id))
        differences = []
        for account in Account.objects.filter(tenant_id=tenant_id).order_by("id"):
            projection = Balance.objects.filter(account=account).first()
            current = projection.amount if projection else None
            actual = expected.get(account.id, 0)
            if current != actual:
                differences.append(
                    {"account": str(account.id), "projection": current, "replay": actual}
                )
            if rebuild:
                Balance.objects.update_or_create(account=account, defaults={"amount": actual})
        return {"consistent": not differences, "differences": differences, "rebuilt": rebuild}

    return retry_transaction(execute)


def lock_waits() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
