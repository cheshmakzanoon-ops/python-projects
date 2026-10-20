"""HTTP Basic (Django password verification) JSON API; tenant header is verified.

Every request requires both Basic credentials and an explicit tenant header;
Django session cookies do not authorize these routes. Use TLS outside loopback.
"""

import base64
import binascii
from uuid import UUID

from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist, RequestDataTooBig
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from pp_meridian.api.validation import json_object, pagination
from pp_meridian.application import ledger, reconcile
from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.domain.money import parse_amount
from pp_meridian.persistence.models import Account, Journal, Posting, ReconciliationRun


def journal_data(journal: Journal) -> dict[str, object]:
    return {
        "id": str(journal.id),
        "journal_id": str(journal.id),
        "tenant_id": str(journal.tenant_id),
        "currency": journal.currency,
        "sequence": journal.sequence,
        "reference": journal.reference,
        "reversal_of": str(journal.reversal_of_id) if journal.reversal_of_id else None,
        "postings": [
            {"id": str(p.id), "account_id": str(p.account_id), "minor_units": p.amount}
            for p in journal.postings.order_by("id")
        ],
    }


def principal(request: HttpRequest) -> tuple[int, UUID]:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Basic "):
        raise ledger.Forbidden("HTTP Basic authentication required")
    try:
        username, password = (
            base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)
        )
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise ledger.Forbidden("invalid authentication") from error
    user = authenticate(request, username=username, password=password)
    if user is None:
        raise ledger.Forbidden("invalid authentication")
    tenant = UUID(request.headers.get("X-Tenant-ID", ""))
    ledger.authorize(user.pk, tenant)
    return user.pk, tenant


def _text(data: dict[str, object], key: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _identity(data: dict[str, object], key: str) -> UUID:
    return UUID(_text(data, key))


def _page(request: HttpRequest) -> tuple[int, int]:
    return pagination(request.GET.get("offset", "0"), request.GET.get("limit", "50"))


@csrf_exempt
@never_cache
def endpoint(request: HttpRequest, operation: str, identity: UUID | None = None) -> JsonResponse:
    try:
        user, tenant = principal(request)
        expected = "GET" if operation in {"journal", "balance", "run_detail"} else "POST"
        if request.method != expected:
            response = JsonResponse({"error": "method not allowed"}, status=405)
            response["Allow"] = expected
            return response
        data = json_object(request.body)
        if operation == "accounts":
            account = ledger.create_account(
                user, tenant, _text(data, "name"), _text(data, "currency")
            )
            return JsonResponse(
                {
                    "id": str(account.id),
                    "account_id": str(account.id),
                    "currency": account.currency,
                },
                status=201,
            )
        if operation == "post":
            currency = _text(data, "currency")
            entries = data.get("postings")
            if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
                raise ValueError("postings list required")
            postings = tuple(
                Entry(_identity(e, "account_id"), parse_amount(e.get("amount"), currency))
                for e in entries
            )
            journal = ledger.post(
                user,
                JournalValue(tenant, currency, postings, _text(data, "reference", "")),
                request.headers.get("Idempotency-Key", ""),
            )
            return JsonResponse(journal_data(journal), status=201)
        if operation == "reversal":
            assert identity is not None
            return JsonResponse(
                journal_data(
                    ledger.reverse(
                        user, tenant, identity, request.headers.get("Idempotency-Key", "")
                    )
                ),
                status=201,
            )
        if operation == "journal":
            assert identity is not None
            return JsonResponse(journal_data(Journal.objects.get(id=identity, tenant_id=tenant)))
        if operation == "balance":
            assert identity is not None
            sequence = request.GET.get("as_of_sequence")
            return JsonResponse(
                {
                    "account_id": str(identity),
                    "minor_units": ledger.balance(
                        user, tenant, identity, int(sequence) if sequence is not None else None
                    ),
                }
            )
        if operation == "import":
            rows = data.get("rows")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("rows list required")
            return JsonResponse(
                {
                    "rows": [
                        str(i)
                        for i in reconcile.import_rows(
                            user, tenant, _identity(data, "account_id"), _text(data, "source"), rows
                        )
                    ]
                },
                status=201,
            )
        if operation == "run":
            row_ids = data.get("row_ids")
            if row_ids is not None and (
                not isinstance(row_ids, list) or not all(isinstance(item, str) for item in row_ids)
            ):
                raise ValueError("row_ids must be a list of UUID strings")
            result = reconcile.run(
                user,
                tenant,
                _identity(data, "account_id"),
                [UUID(item) for item in row_ids] if row_ids is not None else None,
            )
            return JsonResponse({"id": str(result.id), "summary": result.summary}, status=201)
        if operation == "run_detail":
            assert identity is not None
            result = ReconciliationRun.objects.get(id=identity, account__tenant_id=tenant)
            offset, limit = _page(request)
            return JsonResponse(
                {
                    "id": str(result.id),
                    "summary": result.summary,
                    "offset": offset,
                    "limit": limit,
                    "count": result.proposals.count(),
                    "proposals": [
                        {
                            "id": str(p.id),
                            "row_id": str(p.row_id),
                            "posting_id": str(p.posting_id),
                            "ambiguous": p.ambiguous,
                            "status": p.status,
                        }
                        for p in result.proposals.order_by("id")[offset : offset + limit]
                    ],
                }
            )
        if operation == "decision":
            assert identity is not None
            proposal = reconcile.decide(user, tenant, identity, _text(data, "decision"))
            return JsonResponse({"id": str(proposal.id), "status": proposal.status})
        raise ValueError("unknown operation")
    except ledger.Forbidden as error:
        response = JsonResponse({"error": str(error)}, status=403)
        response["WWW-Authenticate"] = 'Basic realm="Meridian"'
        return response
    except ObjectDoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    except ledger.Conflict as error:
        return JsonResponse({"error": str(error)}, status=409)
    except (ValueError, TypeError, KeyError, RequestDataTooBig) as error:
        return JsonResponse({"error": str(error)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "database invariant rejected request"}, status=409)


@never_cache
def screen(request: HttpRequest, kind: str, identity: UUID) -> HttpResponse:
    try:
        user, tenant = principal(request)
        if request.method != "GET":
            response = HttpResponse("Method not allowed", status=405, content_type="text/plain")
            response["Allow"] = "GET"
            return response
        offset, limit = _page(request)
        context: dict[str, object] = {
            "kind": kind,
            "identity": str(identity),
            "tenant": str(tenant),
        }
        has_more = False
        if kind == "journal":
            journal = Journal.objects.get(id=identity, tenant_id=tenant)
            context["journal"] = journal_data(journal)
        elif kind == "account":
            account = Account.objects.get(id=identity, tenant_id=tenant)
            history = list(
                Posting.objects.filter(account=account)
                .select_related("journal")
                .order_by("journal__sequence")[offset : offset + limit + 1]
            )
            has_more = len(history) > limit
            context.update(
                {
                    "account": account,
                    "balance": ledger.balance(user, tenant, identity),
                    "history": history[:limit],
                }
            )
        else:
            run = ReconciliationRun.objects.get(id=identity, account__tenant_id=tenant)
            proposals = list(
                run.proposals.select_related("row", "posting").order_by("id")[
                    offset : offset + limit + 1
                ]
            )
            has_more = len(proposals) > limit
            context.update({"run": run, "proposals": proposals[:limit]})
        context.update(
            {
                "offset": offset,
                "previous": max(0, offset - limit),
                "next": offset + limit,
                "limit": limit,
                "has_more": has_more,
            }
        )
        response = render(
            request,
            "meridian/review.html",
            context,
        )
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'"
        )
        return response
    except ledger.Forbidden:
        return HttpResponse("Verified membership required", status=403, content_type="text/plain")
    except ObjectDoesNotExist:
        return HttpResponse("Not found", status=404, content_type="text/plain")
    except ValueError as error:
        return HttpResponse(str(error), status=400, content_type="text/plain")
