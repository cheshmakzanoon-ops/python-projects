"""Idempotent imports and transactional cross-run approval uniqueness."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from django.db import IntegrityError, transaction

from pp_meridian.application.ledger import Conflict, authorize
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
from pp_meridian.reconciliation.candidates import MatchEntry, candidates
from pp_meridian.reconciliation.normalize import normalize_row


def import_rows(
    user_id: int,
    tenant_id: UUID,
    account_id: UUID,
    source: str,
    rows: Sequence[Mapping[str, object]],
) -> list[UUID]:
    authorize(user_id, tenant_id)
    if not source or len(source) > 200 or len(rows) > 10000:
        raise ValueError("invalid source or more than 10000 rows")
    normalized = [normalize_row(row) for row in rows]
    with transaction.atomic():
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


def run(user_id: int, tenant_id: UUID, account_id: UUID) -> ReconciliationRun:
    authorize(user_id, tenant_id)
    with transaction.atomic():
        account = Account.objects.select_for_update().get(id=account_id, tenant_id=tenant_id)
        rows = list(StatementRow.objects.filter(account=account, approvedmatch__isnull=True))
        postings = list(
            Posting.objects.filter(account=account, approvedmatch__isnull=True).select_related(
                "journal"
            )
        )
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
    authorize(user_id, tenant_id)
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    try:
        with transaction.atomic():
            proposal = Proposal.objects.select_for_update().get(
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
        raise Conflict("row or posting already consumed by another run") from error
