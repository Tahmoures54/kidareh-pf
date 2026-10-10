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
