"""Regression tests for application configuration and infrastructure endpoints."""
from pathlib import Path

from kidareh import create_app


def make_app(tmp_path: Path):
    database_path = tmp_path / "data" / "kidareh.sqlite3"
    upload_folder = tmp_path / "uploads"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-that-is-not-used-in-production",
            "DATABASE_PATH": str(database_path),
            "UPLOAD_FOLDER": str(upload_folder),
        }
    )
    return app, database_path, upload_folder


def test_health_endpoint_checks_database_and_upload_storage(tmp_path):
    app, database_path, upload_folder = make_app(tmp_path)

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["database"] == "ok"
    assert payload["uploads"] == "writable"
    assert database_path.exists()
    assert upload_folder.is_dir()


def test_api_unknown_route_returns_json_not_html(tmp_path):
    app, _, _ = make_app(tmp_path)

    response = app.test_client().get("/api/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "not_found"


def test_upload_endpoint_rejects_unapproved_extension(tmp_path):
    app, _, _ = make_app(tmp_path)

    response = app.test_client().get("/static/uploads/payload.exe")

    assert response.status_code == 404
