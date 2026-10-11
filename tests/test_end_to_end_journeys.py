"""End-to-end journeys and regression guards for the defects fixed after review.

Each test here failed against the code as reviewed (or would have caught the
defect), so they protect the exact behaviour that was repaired:

* duplicate blueprint routes silently shadowing a page handler,
* accounts auto-created with a placeholder name instead of the entered profile,
* SQLite connections left open by the request path,
* feature tables created while serving a request instead of at start-up,
* ISO timestamps compared against SQLite's ``CURRENT_TIMESTAMP``.
"""
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from kidareh import create_app
from kidareh.core import get_connection, initialize_database


@pytest.fixture()
def app(tmp_path, monkeypatch):
    # Deterministic fixtures: demo listings/stores would shift the row ids.
    monkeypatch.setenv("KIDAREH_SEED_DEMO_DATA", "0")

    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "journey-test-secret",
            "DATABASE_PATH": str(tmp_path / "instance" / "journey.sqlite3"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    with application.app_context():
        initialize_database()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


CSRF = "journey-csrf"


def _prime_session(client, **extra):
    """Seed the CSRF token the API expects, as a rendered page would."""
    with client.session_transaction() as session:
        session["csrf_token"] = CSRF
        session.update(extra)


def _answer_challenge(client):
    question = client.get("/api/auth/challenge").get_json()["question"]
    numbers = re.search(r"(\d+)\s*\+\s*(\d+)", question)
    assert numbers
    return str(int(numbers.group(1)) + int(numbers.group(2)))


def _request_otp(client, phone, monkeypatch, **extra):
    """Send an OTP with the SMS provider stubbed out and return the code."""
    import kidareh.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "send_otp", lambda _phone, _code: True)
    client.application.config["TESTING_OTP_CODE"] = True
    _prime_session(client)

    payload = {"phone": phone, "captcha_answer": _answer_challenge(client), "terms_accepted": True}
    payload.update(extra)
    response = client.post(
        "/api/auth/request-otp", json=payload, headers={"X-CSRF-Token": "journey-csrf"}
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["test_code"]


# --- Routing -----------------------------------------------------------------


def test_no_two_blueprints_claim_the_same_page(app):
    """A shadowed page handler renders the wrong context (packages went missing)."""
    owners = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        owners.setdefault(rule.rule, set()).add(rule.endpoint)

    cross_blueprint = {
        url: sorted(endpoints)
        for url, endpoints in owners.items()
        if len({endpoint.split(".")[0] for endpoint in endpoints}) > 1
    }
    assert cross_blueprint == {}


def test_monetization_page_renders_every_purchasable_package(client, app):
    from kidareh.routes.monetization import PACKAGES

    with app.app_context():
        with get_connection() as connection:
            user_id = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("فروشنده آزمایشی", "09120000005", "test-hash", "seller"),
            ).lastrowid
    with client.session_transaction() as session:
        session["user_id"] = user_id

    response = client.get("/monetization")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    for package in PACKAGES:
        assert f'data-package="{package["id"]}"' in body, package["id"]


# --- Seller registration journey ---------------------------------------------


def test_seller_signup_uses_the_details_entered_in_the_profile_step(app, client, monkeypatch):
    code = _request_otp(client, "09121110000", monkeypatch, registering=True, role="seller")

    verified = client.post(
        "/api/auth/verify-otp", json={"code": code}, headers={"X-CSRF-Token": "journey-csrf"}
    )
    assert verified.status_code == 200
    payload = verified.get_json()
    assert payload["existing_user"] is False
    assert payload["phone"] == "09121110000"

    created = client.post(
        "/api/auth/complete-profile",
        headers={"X-CSRF-Token": "journey-csrf"},
        json={
            "name": "سارا احمدی",
            "role": "seller",
            "store_name": "ویترین سارا",
            "store_category": "لوازم خانه",
            "store_city": "تهران",
            "store_address": "تهران، خیابان نمونه",
            "store_hours": "۹ تا ۱۸",
            "in_person": True,
        },
    )
    assert created.status_code == 200, created.get_json()
    user = created.get_json()["user"]
    store = created.get_json()["store"]

    assert user["name"] == "سارا احمدی"
    assert user["role"] == "seller"
    assert store["name"] == "ویترین سارا"

    # The seller can immediately publish a product into the store they created.
    csrf = created.get_json()["csrf_token"]
    product = client.post(
        "/api/listings",
        headers={"X-CSRF-Token": csrf},
        json={
            "title": "میز کار چوبی",
            "category": "home",
            "city": "تهران",
            "price": 2450000,
            "description": "میز مرتب و خوش‌ساخت",
        },
    )
    assert product.status_code == 201, product.get_json()
    assert product.get_json()["item"]["store_id"] == store["id"]

    detail = client.get(f"/product/{product.get_json()['item']['id']}")
    assert detail.status_code == 200


def test_buyer_signup_validates_the_residential_city(app, client, monkeypatch):
    code = _request_otp(client, "09121110001", monkeypatch, registering=True, role="buyer")
    client.post(
        "/api/auth/verify-otp", json={"code": code}, headers={"X-CSRF-Token": "journey-csrf"}
    )

    rejected = client.post(
        "/api/auth/complete-profile",
        headers={"X-CSRF-Token": "journey-csrf"},
        json={"name": "خریدار تازه", "role": "buyer", "city": "شهر خیالی"},
    )
    assert rejected.status_code == 400
    assert rejected.get_json()["error"] == "invalid_city"

    accepted = client.post(
        "/api/auth/complete-profile",
        headers={"X-CSRF-Token": "journey-csrf"},
        json={"name": "خریدار تازه", "role": "buyer", "city": "تهران"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["user"]["city"] == "تهران"


# --- Database plumbing --------------------------------------------------------


def test_database_connection_is_closed_after_use(app, monkeypatch):
    opened = []
    original_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    with app.app_context():
        with get_connection() as connection:
            connection.execute("SELECT 1")

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


def test_database_connection_commits_on_success(app):
    with app.app_context():
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("ذخیره‌شده", "09121110002", "hash", "buyer"),
            )
        with get_connection() as connection:
            assert connection.execute(
                "SELECT 1 FROM users WHERE phone = ?", ("09121110002",)
            ).fetchone() is not None


def test_feature_tables_are_created_at_startup(app):
    """Report and rate-limit tables must not be created while serving a request."""
    with app.app_context():
        with get_connection() as connection:
            tables = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }

    assert {"otp_rate_limits", "content_reports"} <= tables


def test_report_endpoint_does_not_run_schema_statements(app, client, monkeypatch):
    statements = []
    original_connect = sqlite3.connect

    def tracing_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    _prime_session(client, user_id=1)

    with app.app_context():
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at)"
                " VALUES ('گزارش‌دهنده', '09121110003', 'hash', 'buyer', ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
            connection.execute(
                "INSERT INTO listings (title, category, city, price) VALUES ('کالا', 'home', 'تهران', 1000)"
            )

    monkeypatch.setattr(sqlite3, "connect", tracing_connect)
    response = client.post(
        "/api/reports",
        headers={"X-CSRF-Token": "journey-csrf"},
        json={"target_type": "listing", "target_id": 1, "reason": "spam", "details": "تست"},
    )

    assert response.status_code == 201
    schema_statements = [
        statement
        for statement in statements
        if "CREATE TABLE" in statement.upper() or "CREATE INDEX" in statement.upper()
    ]
    assert schema_statements == []


# --- Timestamps ---------------------------------------------------------------


def test_expired_store_promotion_is_not_reported_active(app, client):
    now = datetime.now(timezone.utc)
    expired = (now - timedelta(hours=5)).isoformat()   # expired earlier today
    live = (now + timedelta(days=2)).isoformat()

    with app.app_context():
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at)"
                " VALUES ('فروشنده', '09121110004', 'hash', 'seller', ?)",
                (now.isoformat(),),
            )
            connection.execute("INSERT INTO stores (owner_id, name, city) VALUES (1, 'ویترین', 'تهران')")
            connection.execute(
                "INSERT INTO store_promotions (store_id, user_id, package_id, starts_at, ends_at, status)"
                " VALUES (1, 1, 'market_story_1d', ?, ?, 'active')",
                (expired, expired),
            )
            connection.execute(
                "INSERT INTO store_promotions (store_id, user_id, package_id, starts_at, ends_at, status)"
                " VALUES (1, 1, 'homepage_banner_7d', ?, ?, 'active')",
                (expired, live),
            )

    _prime_session(client, user_id=1)
    payload = client.get("/api/monetization/status").get_json()
    assert [promotion["package_id"] for promotion in payload["promotions"]] == ["homepage_banner_7d"]


# --- Concurrent start-up ------------------------------------------------------


def _initialize_in_child(database_path, upload_folder, outcomes):
    """Run initialize_database() in a forked worker, as a Gunicorn worker would."""
    os.environ["DATABASE_PATH"] = database_path
    os.environ["UPLOAD_FOLDER"] = upload_folder
    os.environ["KIDAREH_SEED_DEMO_DATA"] = "0"
    try:
        from flask import Flask

        from kidareh.core import initialize_database

        worker_app = Flask(__name__)
        worker_app.config.update(
            DATABASE_PATH=database_path,
            UPLOAD_FOLDER=upload_folder,
        )
        with worker_app.app_context():
            initialize_database()
        outcomes.put("ok")
    except Exception as error:  # pragma: no cover - reported through the queue
        outcomes.put(f"{type(error).__name__}: {error}")


def test_concurrent_schema_initialization_does_not_crash_workers(tmp_path):
    """Four workers booting at once used to collide on the migration ledger."""
    import multiprocessing
    import os

    if not hasattr(os, "fork"):  # pragma: no cover - Windows/macOS spawn platforms
        pytest.skip("fork-based worker simulation is unavailable")

    outcomes = multiprocessing.Queue()
    workers = [
        multiprocessing.Process(
            target=_initialize_in_child,
            args=(str(tmp_path / "concurrent.sqlite3"), str(tmp_path / "up"), outcomes),
        )
        for _ in range(4)
    ]
    for worker in workers:
        worker.start()
    results = [outcomes.get(timeout=120) for _ in workers]
    for worker in workers:
        worker.join(timeout=30)

    assert results == ["ok"] * 4, results
