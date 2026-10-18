from django.urls import path

from pp_meridian.api.views import endpoint, screen

urlpatterns = [
    path("api/v1/accounts", endpoint, {"operation": "accounts"}),
    path("api/v1/journals", endpoint, {"operation": "post"}),
    path("api/v1/journals/<uuid:identity>", endpoint, {"operation": "journal"}),
    path("api/v1/journals/<uuid:identity>/reversal", endpoint, {"operation": "reversal"}),
    path("api/v1/accounts/<uuid:identity>/balance", endpoint, {"operation": "balance"}),
    path("api/v1/statements/import", endpoint, {"operation": "import"}),
    path("api/v1/reconciliation/runs", endpoint, {"operation": "run"}),
    path("api/v1/reconciliation/runs/<uuid:identity>", endpoint, {"operation": "run_detail"}),
    path(
        "api/v1/reconciliation/proposals/<uuid:identity>/decision",
        endpoint,
        {"operation": "decision"},
    ),
    path("journals/<uuid:identity>", screen, {"kind": "journal"}),
    path("accounts/<uuid:identity>", screen, {"kind": "account"}),
    path("reconciliation/<uuid:identity>", screen, {"kind": "reconciliation"}),
]
