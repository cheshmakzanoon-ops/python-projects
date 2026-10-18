from collections.abc import Iterator
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from pp_meridian.application.ledger import create_account
from pp_meridian.persistence.models import Membership, Tenant


@pytest.fixture
def ledger(db: None) -> Iterator[tuple[int, Tenant, list[object]]]:
    user = get_user_model().objects.create_user(
        username=str(uuid4()), password="synthetic-password"
    )
    tenant = Tenant.objects.create(name="Synthetic equipment rental")
    Membership.objects.create(user=user, tenant=tenant, verified=True)
    accounts = [
        create_account(user.pk, tenant.id, name, "USD") for name in ["bank", "receivable", "income"]
    ]
    yield user.pk, tenant, accounts
