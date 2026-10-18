import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    last_sequence = models.BigIntegerField(default=0)


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "tenant"], name="unique_member")]


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    currency = models.CharField(max_length=3)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency__in=["USD", "CAD", "EUR", "JPY", "KWD"]),
                name="account_currency",
            )
        ]


class Journal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    currency = models.CharField(max_length=3)
    sequence = models.BigIntegerField(default=0)
    reference = models.CharField(max_length=200, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    reversal_of = models.OneToOneField(
        "self", null=True, on_delete=models.PROTECT, related_name="reversal"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "sequence"], name="tenant_sequence"),
            models.UniqueConstraint(fields=["id", "tenant"], name="journal_identity_tenant"),
        ]


class Posting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="postings")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    amount = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(amount=0) & models.Q(amount__gte=-(10**15), amount__lte=10**15)
                ),
                name="bounded_posting",
            ),
            models.UniqueConstraint(fields=["journal", "account"], name="journal_account"),
        ]


class Balance(models.Model):
    account = models.OneToOneField(Account, primary_key=True, on_delete=models.PROTECT)
    amount = models.BigIntegerField(default=0)


class Idempotency(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    key = models.CharField(max_length=200)
    payload_hash = models.CharField(max_length=64)
    journal = models.OneToOneField(Journal, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "key"], name="tenant_idempotency")]


class StatementRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    source = models.CharField(max_length=200)
    identity = models.CharField(max_length=200)
    payload_hash = models.CharField(max_length=64)
    amount = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    timestamp = models.DateTimeField()
    reference = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "source", "identity"], name="statement_identity"
            )
        ]


class ReconciliationRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=dict)


class Proposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ReconciliationRun, on_delete=models.PROTECT, related_name="proposals")
    row = models.ForeignKey(StatementRow, on_delete=models.PROTECT)
    posting = models.ForeignKey(Posting, on_delete=models.PROTECT)
    ambiguous = models.BooleanField(default=False)
    status = models.CharField(max_length=12, default="pending")


class ApprovedMatch(models.Model):
    proposal = models.OneToOneField(Proposal, primary_key=True, on_delete=models.PROTECT)
    row = models.OneToOneField(StatementRow, on_delete=models.PROTECT)
    posting = models.OneToOneField(Posting, on_delete=models.PROTECT)


class DecisionAudit(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=12)
    timestamp = models.DateTimeField(auto_now_add=True)
