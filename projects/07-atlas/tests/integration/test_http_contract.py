"""HTTP resource bounds, browser privacy policy and opaque document identities."""

from html.parser import HTMLParser
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from pp_atlas import Document, Engine, Principal
from pp_atlas.api import Identity, create_app

TOKEN = "synthetic-reader-token"
AUTH = {"Authorization": "Bearer " + TOKEN}


def client_for(engine, *, admin=False):
    return TestClient(create_app(engine, {TOKEN: Identity(Principal("docs", "reader"), admin)}))


def test_export_only_materializes_requested_page_with_authorized_total(tmp_path, monkeypatch):
    import pp_atlas.engine as module

    engine = Engine(tmp_path)
    engine.upsert_many(
        "docs",
        [Document(f"public-{n:03d}", str(n), "visible") for n in range(35)]
        + [Document("private", "Private", "hidden", frozenset({"user:admin"}))],
    )
    instantiated = []
    original = module.Document

    def counted(*args, **kwargs):
        document = original(*args, **kwargs)
        instantiated.append(document.id)
        return document

    monkeypatch.setattr(module, "Document", counted)
    with client_for(engine) as client:
        response = client.get("/export?limit=3&offset=10", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 35
    expected = ["public-010", "public-011", "public-012"]
    assert [document["id"] for document in data["documents"]] == instantiated == expected
    assert all("acl" not in document for document in data["documents"])


def test_export_page_observes_next_request_revocation(tmp_path):
    writer, reader = Engine(tmp_path), Engine(tmp_path)
    writer.upsert("docs", Document("x", "x", "restricted", frozenset({"group:ops"})))
    writer.set_groups("docs", "reader", ["ops"])
    principal = Principal("docs", "reader")
    total, documents = reader.export_page(principal)
    assert total == 1 and [document.id for document in documents] == ["x"]
    writer.set_groups("docs", "reader", [])
    assert reader.export_page(principal) == (0, ())


@pytest.mark.parametrize("limit,offset", [(True, 0), (1.5, 0), (1, True), (1, 1.5)])
def test_pagination_requires_exact_integer_values(tmp_path, limit, offset):
    engine = Engine(tmp_path)
    principal = Principal("docs", "reader")
    for operation in (engine.search, engine.export_page):
        with pytest.raises(ValueError, match="integer"):
            if operation == engine.search:
                operation(principal, "", limit=limit, offset=offset)
            else:
                operation(principal, limit=limit, offset=offset)


@pytest.mark.parametrize(
    "document_id", ["runbooks/recovery", "../opaque-document", "space and ? #"]
)
def test_http_document_ids_remain_opaque_data(tmp_path, document_id):
    engine = Engine(tmp_path)
    engine.upsert("docs", Document(document_id, "Read me", "recoverable"))
    path = "/documents/" + quote(document_id, safe="")
    with client_for(engine, admin=True) as client:
        assert client.get(path, headers=AUTH).json()["text"] == "recoverable"
        response = client.put(path + "/acl", headers=AUTH, json={"subjects": ["user:other"]})
        assert response.status_code == 200
        assert client.get(path, headers=AUTH).status_code == 404
        assert client.delete(path, headers=AUTH).json() == {"deleted": True}


@pytest.mark.parametrize("admin", ["false", "true", 0, 1, None])
def test_admin_bindings_cannot_use_truthy_non_booleans(admin):
    with pytest.raises(ValueError, match="boolean"):
        Identity(Principal("docs", "reader"), admin)


def test_browser_assets_privacy_headers_and_auth_errors(tmp_path):
    engine = Engine(tmp_path)
    with client_for(engine) as client:
        view = client.get("/")
        assert view.status_code == 200
        assert "unsafe-inline" not in view.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in view.headers["content-security-policy"]
        assert '<script src="/assets/search.js" defer>' in view.text
        assert '<label for="query">' in view.text
        for path in (
            "/",
            "/assets/search.js",
            "/assets/search.css",
            "/search",
            "/search?q=missing",
        ):
            response = client.get(path)
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["x-frame-options"] == "DENY"
        assert client.get("/search", headers=AUTH).headers["cache-control"] == "no-store"


def test_oversized_chunked_json_is_413_before_fastapi_parsing(tmp_path):
    def body():
        yield b'{"id":"streamed","text":"'
        yield b"x" * 2_100_000
        yield b'"}'

    with client_for(Engine(tmp_path), admin=True) as client:
        response = client.post(
            "/documents", headers={**AUTH, "Content-Type": "application/json"}, content=body()
        )
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_credentials_cannot_fall_back_to_native_form_url_submission(tmp_path):
    controls = {}

    class Controls(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if "id" in attributes:
                controls[attributes["id"]] = attributes

    with client_for(Engine(tmp_path)) as client:
        Controls().feed(client.get("/").text)
    # If the script fails or is disabled, native form submission must never
    # include a credential in a URL. Script initialization enables searching.
    assert "name" not in controls["token"]
    assert "disabled" in controls["search-button"]
