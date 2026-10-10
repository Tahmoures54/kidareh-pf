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


def test_production_rejects_default_secret_key(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("LIARA_APP_ID", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    import pytest

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        create_app()


def test_production_enables_secure_session_cookie(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-test-secret-key")
    app, _, _ = make_app(tmp_path)

    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_database_initialization_is_repeatable_and_uses_app_config(monkeypatch, tmp_path):
    from kidareh.core import get_connection, initialize_database

    monkeypatch.setenv("KIDAREH_SEED_DEMO_DATA", "0")
    app, database_path, _ = make_app(tmp_path)

    with app.app_context():
        initialize_database()
        initialize_database()
        with get_connection() as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert {"users", "stores", "listings", "saved_products"} <= tables
            assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

    assert database_path.exists()


def test_auth_mutation_requires_csrf_token(tmp_path):
    app, _, _ = make_app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/auth/request-otp",
        json={
            "phone": "09123456789",
            "registering": True,
            "role": "buyer",
            "captcha_answer": "1",
            "terms_accepted": True,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "csrf_failed"
