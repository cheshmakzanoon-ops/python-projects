"""Idempotent imports and transactional cross-run approval uniqueness."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timezone
from uuid import UUID

from django.db import IntegrityError, transaction

from pp_meridian.application.ledger import Conflict, lock_authorization
from pp_meridian.persistence.models import (
    Account,
    ApprovedMatch,
    DecisionAudit,
    Posting,
    Proposal,
    ReconciliationRun,
    StatementRow,
)
from pp_meridian.reconciliation.assignment import solve
from pp_meridian.reconciliation.candidates import DEFAULT_WINDOW_DAYS, MatchEntry, candidates
from pp_meridian.reconciliation.normalize import normalize_row

MAX_RUN_ROWS = 10_000
MAX_RUN_POSTINGS = 50_000


def import_rows(
    user_id: int,
    tenant_id: UUID,
    account_id: UUID,
    source: str,
    rows: Sequence[Mapping[str, object]],
) -> list[UUID]:
    if not source or len(source) > 200 or len(rows) > 10000:
        raise ValueError("invalid source or more than 10000 rows")
    normalized = [normalize_row(row) for row in rows]
    with transaction.atomic():
        lock_authorization(user_id, tenant_id)
        account = Account.objects.select_for_update().get(id=account_id, tenant_id=tenant_id)
        result = []
        for row in normalized:
            if row.currency != account.currency:
                raise ValueError("statement currency mismatch")
            existing = StatementRow.objects.filter(
                account=account, source=source, identity=row.identity
            ).first()
            if existing:
                if existing.payload_hash != row.payload_hash:
                    raise Conflict("statement identity payload mismatch")
                result.append(existing.id)
                continue
            created = StatementRow.objects.create(
                account=account,
                source=source,
                identity=row.identity,
                payload_hash=row.payload_hash,
                amount=row.amount,
                currency=row.currency,
                timestamp=row.timestamp,
                reference=row.reference,
            )
            result.append(created.id)
        return result


def run(
    user_id: int,
    tenant_id: UUID,
    account_id: UUID,
    row_ids: Sequence[UUID] | None = None,
) -> ReconciliationRun:
    if row_ids is not None and (len(row_ids) > MAX_RUN_ROWS or len(set(row_ids)) != len(row_ids)):
        raise ValueError("row_ids must be unique and contain at most 10000 identities")
    with transaction.atomic():
        lock_authorization(user_id, tenant_id)
        account = Account.objects.select_for_update().get(id=account_id, tenant_id=tenant_id)
        selected = StatementRow.objects.filter(account=account, approvedmatch__isnull=True)
        if row_ids is not None:
            selected = selected.filter(id__in=row_ids)
        rows = list(selected.order_by("id")[: MAX_RUN_ROWS + 1])
        if len(rows) > MAX_RUN_ROWS:
            raise ValueError("run exceeds 10000 rows; select a row_ids batch")
        if row_ids is not None and len(rows) != len(row_ids):
            raise ValueError("selected rows must be unmatched rows in this account")
        eligible = (
            Posting.objects.filter(
                account=account,
                approvedmatch__isnull=True,
                amount__in={row.amount for row in rows},
            )
            .select_related("journal")
            .order_by("id")
        )
        if rows:
            first = max(
                date.min.toordinal(),
                min(r.timestamp.date().toordinal() for r in rows) - DEFAULT_WINDOW_DAYS,
            )
            last = min(
                date.max.toordinal(),
                max(r.timestamp.date().toordinal() for r in rows) + DEFAULT_WINDOW_DAYS,
            )
            eligible = eligible.filter(
                journal__created_at__gte=datetime.combine(
                    date.fromordinal(first), time.min, timezone.utc
                )
            )
            if last < date.max.toordinal():
                eligible = eligible.filter(
                    journal__created_at__lt=datetime.combine(
                        date.fromordinal(last + 1), time.min, timezone.utc
                    )
                )
        postings = list(eligible[: MAX_RUN_POSTINGS + 1])
        if len(postings) > MAX_RUN_POSTINGS:
            raise ValueError("run exceeds 50000 eligible postings; select a smaller row_ids batch")
        left = [MatchEntry(str(r.id), r.amount, r.currency, r.timestamp, r.reference) for r in rows]
        right = [
            MatchEntry(
                str(p.id), p.amount, p.journal.currency, p.journal.created_at, p.journal.reference
            )
            for p in postings
        ]
        edges = candidates(left, right)
        assignments = solve([r.identity for r in left], edges)
        result = ReconciliationRun.objects.create(
            account=account,
            summary={
                "rows": len(rows),
                "selected_row_ids": [str(row.id) for row in rows],
                "postings": len(postings),
                "edges": len(edges),
                "components": len(assignments),
                "ambiguous_components": sum(a.ambiguous for a in assignments),
                "cost": sum(a.cost for a in assignments),
            },
        )
        Proposal.objects.bulk_create(
            [
                Proposal(
                    run=result, row_id=UUID(left_id), posting_id=UUID(r), ambiguous=a.ambiguous
                )
                for a in assignments
                for left_id, r in a.pairs
            ]
        )
        return result


def decide(user_id: int, tenant_id: UUID, proposal_id: UUID, decision: str) -> Proposal:
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    try:
        with transaction.atomic():
            lock_authorization(user_id, tenant_id)
            proposal = Proposal.objects.select_for_update(of=("self",)).get(
                id=proposal_id, run__account__tenant_id=tenant_id
            )
            if proposal.status != "pending":
                raise Conflict("stale proposal")
            if decision == "approve":
                ApprovedMatch.objects.create(
                    proposal=proposal, row_id=proposal.row_id, posting_id=proposal.posting_id
                )
            proposal.status = "approved" if decision == "approve" else "rejected"
            proposal.save(update_fields=["status"])
            DecisionAudit.objects.create(proposal=proposal, user_id=user_id, decision=decision)
            return proposal
    except IntegrityError as error:
        cause = error.__cause__
        if (
            getattr(cause, "sqlstate", None) == "23505"
            and getattr(getattr(cause, "diag", None), "table_name", None)
            == "meridian_approvedmatch"
        ):
            raise Conflict("row or posting already consumed by another run") from error
        # A broken audit/state invariant is not an ordinary competing approval.
        raise
