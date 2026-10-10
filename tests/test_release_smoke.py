"""Release smoke tests for the marketplace's public entry points and media storage."""
from pathlib import Path

import pytest

from kidareh import create_app
from kidareh.core import initialize_database


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "instance" / "test.sqlite3"
    upload_folder = tmp_path / "persistent-uploads"
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE_PATH": str(database_path),
        "UPLOAD_FOLDER": str(upload_folder),
    })
    with application.app_context():
        initialize_database()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_core_pages_render(client):
    for path in ("/", "/login", "/register", "/seller", "/stores", "/messages", "/support"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_health_reports_database_and_upload_readiness(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["database"] == "ok"
    assert payload["uploads"] == "writable"


def test_uploaded_image_route_serves_configured_upload_folder(app, client):
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    image_bytes = b"\x89PNG\r\n\x1a\nsmoke-test"
    (upload_folder / "smoke-test.png").write_bytes(image_bytes)

    response = client.get("/static/uploads/smoke-test.png")
    assert response.status_code == 200
    assert response.data == image_bytes


def test_uploaded_image_route_rejects_non_image_extensions(client):
    response = client.get("/static/uploads/not-an-image.txt")
    assert response.status_code == 404



def test_seller_and_paid_features_require_authentication(client):
    assert client.get("/api/my/store").status_code == 401
    assert client.get("/api/monetization/orders").status_code == 401
    assert client.get("/api/support/tickets").status_code == 401


def test_listing_creation_requires_authentication(client):
    response = client.post("/api/listings", json={
        "title": "آگهی آزمایشی",
        "category": "home",
        "city": "تهران",
        "price": 0,
    })
    assert response.status_code == 401


def test_pwa_manifest_is_valid_and_installable(client):
    import json

    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    manifest = json.loads(response.get_data(as_text=True))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/?source=pwa"
    assert manifest["scope"] == "/"
    assert manifest["icons"]


def test_pwa_shell_assets_and_offline_fallback_are_available(client):
    for path in (
        "/static/js/pwa.js",
        "/static/sw.js",
        "/static/offline.html",
    ):
        response = client.get(path)
        assert response.status_code == 200, path

    worker = client.get("/static/sw.js").get_data(as_text=True)
    assert "kidareh-shell-v3" in worker
    assert "/static/offline.html" in worker
    assert "isPrivatePath" in worker


def test_home_and_inner_pages_include_mobile_navigation_and_install_script(client):
    for path in ("/", "/stores", "/login"):
        response = client.get(path)
        html = response.get_data(as_text=True)
        assert 'class="mobile-bottom-nav"' in html, path
        assert 'id="installAppButton"' in html or path == "/login"
        assert 'static/js/pwa.js' in html, path



def test_service_worker_is_available_at_root_scope(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers.get("Service-Worker-Allowed") == "/"
    assert "kidareh-shell-v3" in response.get_data(as_text=True)
