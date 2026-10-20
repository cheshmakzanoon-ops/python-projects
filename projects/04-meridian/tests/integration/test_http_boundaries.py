"""Exercise the public request and operator-view boundaries on PostgreSQL."""

import base64

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from pp_meridian.application import ledger as service
from pp_meridian.application import reconcile
from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.persistence.models import Account

pytestmark = pytest.mark.django_db(transaction=True)


def headers(ledger):
    user_id, tenant, _ = ledger
    username = get_user_model().objects.get(id=user_id).username
    return {
        "HTTP_AUTHORIZATION": "Basic "
        + base64.b64encode(f"{username}:synthetic-password".encode()).decode(),
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.mark.parametrize(
    "body",
    [
        b'{"name":"one","name":"two","currency":"USD"}',
        b'{"name":"unsafe\\ud800","currency":"USD"}',
        b'{"name":"unsafe\\u0000","currency":"USD"}',
        b'{"name":"valid","currency":"USD","ignored":NaN}',
        b'{"name":"valid","currency":"USD","ignored":1e999}',
        b'{"ignored":' + b"[" * 2_000 + b"0" + b"]" * 2_000 + b"}",
    ],
)
def test_invalid_json_returns_validation_error_without_writing(ledger, body):
    before = Account.objects.count()
    response = Client().post(
        "/api/v1/accounts", body, content_type="application/json", **headers(ledger)
    )
    assert response.status_code == 400
    assert "error" in response.json()
    assert Account.objects.count() == before


def test_account_view_has_structured_escaped_history_and_real_pagination(ledger):
    user_id, tenant, accounts = ledger
    account = accounts[0]
    account.name = '<script>alert("account")</script>'
    account.save(update_fields=["name"])
    for sequence in range(2):
        service.post(
            user_id,
            JournalValue(
                tenant.id,
                "USD",
                (Entry(account.id, 100), Entry(accounts[1].id, -100)),
                '<script>alert("reference")</script>',
            ),
            f"view-{sequence}",
        )
    client = Client()
    first = client.get(f"/accounts/{account.id}?limit=1", **headers(ledger))
    assert first.status_code == 200
    content = first.content.decode()
    assert '<th scope="col">Sequence</th>' in content
    assert "&lt;script&gt;" in content and "<script>" not in content
    assert 'rel="next"' in content and 'rel="prev"' not in content
    assert "Skip to record" in content
    assert "no-store" in first["Cache-Control"]
    assert "frame-ancestors 'none'" in first["Content-Security-Policy"]
    last = client.get(f"/accounts/{account.id}?offset=1&limit=1", **headers(ledger))
    assert last.status_code == 200
    assert 'rel="prev"' in last.content.decode()
    assert 'rel="next"' not in last.content.decode()


def test_view_rejects_overflow_pagination_and_advertises_allowed_method(ledger):
    _, _, accounts = ledger
    client = Client()
    path = f"/accounts/{accounts[0].id}"
    assert client.get(f"{path}?offset={2**63}", **headers(ledger)).status_code == 400
    response = client.post(path, **headers(ledger))
    assert response.status_code == 405
    assert response["Allow"] == "GET"
    response = client.get("/api/v1/accounts", **headers(ledger))
    assert response.status_code == 405
    assert response["Allow"] == "POST"


def test_view_validation_error_cannot_render_query_text_as_html(ledger):
    _, _, accounts = ledger
    response = Client().get(
        f"/accounts/{accounts[0].id}",
        {"offset": '<script>alert("offset")</script>'},
        **headers(ledger),
    )
    assert response.status_code == 400
    assert response["Content-Type"].startswith("text/plain")
    assert "no-store" in response["Cache-Control"]


def test_api_responses_do_not_leave_authenticated_history_in_caches(ledger):
    _, _, accounts = ledger
    response = Client().get(f"/api/v1/accounts/{accounts[0].id}/balance", **headers(ledger))
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


def test_journal_and_reconciliation_views_show_reviewable_records(ledger):
    user_id, tenant, accounts = ledger
    journal = service.post(
        user_id,
        JournalValue(
            tenant.id,
            "USD",
            (Entry(accounts[0].id, 100), Entry(accounts[1].id, -100)),
            "INV-100",
        ),
        "review-record",
    )
    reconcile.import_rows(
        user_id,
        tenant.id,
        accounts[0].id,
        "bank",
        [
            {
                "id": f"row-{number}",
                "currency": "USD",
                "amount": "1.00",
                "timestamp": journal.created_at.isoformat(),
                "reference": "INV100",
            }
            for number in range(2)
        ],
    )
    run = reconcile.run(user_id, tenant.id, accounts[0].id)
    client = Client()
    journal_response = client.get(f"/journals/{journal.id}", **headers(ledger))
    assert journal_response.status_code == 200
    journal_html = journal_response.content.decode()
    assert "Posted journal" in journal_html and "INV-100" in journal_html
    assert str(accounts[0].id) in journal_html
    assert "Next page" not in journal_html
    run_response = client.get(f"/reconciliation/{run.id}", **headers(ledger))
    assert run_response.status_code == 200
    run_html = run_response.content.decode()
    assert "Ambiguous match" in run_html and "Pending" in run_html
    assert str(run.proposals.get().id) in run_html
