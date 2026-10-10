"""Seller purchase journey: catalogue, order creation and gateway hand-off.

The monetization module carries the money path, so its ordering rules (who may
buy what, and when the gateway is contacted) are covered explicitly here.
"""
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
            "SECRET_KEY": "monetization-test-secret",
            "DATABASE_PATH": str(tmp_path / "instance" / "monetization.sqlite3"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    with application.app_context():
        initialize_database()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seller(client):
    """A signed-in seller that owns a store with one listing."""
    with client.session_transaction() as session:
        session["csrf_token"] = "money-csrf"
        session["user_id"] = 1

    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at)"
                " VALUES ('فروشنده', '09121112222', 'hash', 'seller', 'verified')"
            )
            db.execute("INSERT INTO stores (owner_id, name, city) VALUES (1, 'ویترین', 'تهران')")
            db.execute(
                "INSERT INTO listings (title, category, city, price, owner_id, store_id)"
                " VALUES ('کالای فروشنده', 'home', 'تهران', 1000, 1, 1)"
            )
    return {"user_id": 1, "store_id": 1, "listing_id": 1}


def _order(client, **payload):
    return client.post(
        "/api/monetization/orders",
        headers={"X-CSRF-Token": "money-csrf"},
        json=payload,
    )


def test_packages_endpoint_exposes_store_and_listing_catalogues(client):
    from kidareh.routes.monetization import PACKAGES, TAG_PACKAGES

    payload = client.get("/api/monetization/packages").get_json()

    assert payload["currency"] == "تومان"
    assert {item["id"] for item in payload["items"]} == {
        item["id"] for item in PACKAGES + TAG_PACKAGES
    }
    assert {item["id"] for item in payload["tag_items"]} == {item["id"] for item in TAG_PACKAGES}
    # No merchant configured in the test environment, so payment must be closed.
    assert payload["payment_enabled"] is False


def test_payment_is_unavailable_without_gateway_configuration(client, seller):
    response = _order(client, package_id="blue_tick_30d")

    assert response.status_code == 503
    assert response.get_json()["error"] == "payment_unavailable"


def test_order_creation_requires_authentication(app, tmp_path):
    anonymous = app.test_client()
    response = anonymous.post("/api/monetization/orders", json={"package_id": "blue_tick_30d"})

    assert response.status_code == 401


def test_unknown_package_is_rejected(client, seller):
    response = _order(client, package_id="package-that-does-not-exist")

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_package"


def test_listing_tag_order_requires_an_owned_listing(client, seller, monkeypatch):
    import kidareh.routes.monetization as monetization

    monkeypatch.setenv("ZIBAL_MERCHANT", "test-merchant")
    monkeypatch.setattr(
        monetization, "zibal_request", lambda _url, _payload: {"result": 100, "trackId": "4242"}
    )

    missing = _order(client, package_id="listing_tag_sale")
    assert missing.status_code == 400
    assert missing.get_json()["error"] == "listing_required"

    foreign = _order(client, package_id="listing_tag_sale", listing_id=999)
    assert foreign.status_code == 403
    assert foreign.get_json()["error"] == "listing_forbidden"


def test_successful_order_stores_track_id_and_returns_gateway_url(client, seller, monkeypatch):
    import kidareh.routes.monetization as monetization

    monkeypatch.setenv("ZIBAL_MERCHANT", "test-merchant")
    monkeypatch.setattr(
        monetization, "zibal_request", lambda _url, _payload: {"result": 100, "trackId": "4242"}
    )

    response = _order(client, package_id="listing_tag_sale", listing_id=seller["listing_id"])
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["redirect_url"].endswith("/4242")

    order_id = payload["order_id"]
    with client.application.app_context():
        with get_connection() as db:
            order = db.execute("SELECT * FROM monetization_orders WHERE id=?", (order_id,)).fetchone()

    assert order["status"] == "pending"
    assert order["gateway_code"] == "4242"
    assert order["listing_id"] == seller["listing_id"]
    assert order["amount_toman"] == 19000


def test_failed_gateway_request_marks_the_order_failed(client, seller, monkeypatch):
    import kidareh.routes.monetization as monetization

    monkeypatch.setenv("ZIBAL_MERCHANT", "test-merchant")

    def refuse(_url, _payload):
        raise RuntimeError("gateway refused")

    monkeypatch.setattr(monetization, "zibal_request", refuse)

    response = _order(client, package_id="blue_tick_30d")
    assert response.status_code == 503

    with client.application.app_context():
        with get_connection() as db:
            failed = db.execute(
                "SELECT COUNT(*) FROM monetization_orders WHERE status='failed'"
            ).fetchone()[0]
    assert failed == 1


def test_my_listings_reports_the_active_tag(client, seller):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO listing_tags (listing_id, user_id, tag_type, starts_at, ends_at, status, order_id)"
                " VALUES (?, ?, 'listing_tag_sale', ?, ?, 'active', 1)",
                (
                    seller["listing_id"],
                    seller["user_id"],
                    now.isoformat(),
                    (now + timedelta(days=7)).isoformat(),
                ),
            )

    payload = client.get("/api/my/listings").get_json()
    assert payload["items"][0]["active_tag"] == "listing_tag_sale"
    assert payload["tag_labels"]["listing_tag_sale"] == "حراج"


def test_seller_without_a_store_cannot_buy_a_store_package(client, monkeypatch):
    import kidareh.routes.monetization as monetization

    monkeypatch.setenv("ZIBAL_MERCHANT", "test-merchant")
    monkeypatch.setattr(
        monetization, "zibal_request", lambda _url, _payload: {"result": 100, "trackId": "1"}
    )
    with client.session_transaction() as session:
        session["csrf_token"] = "money-csrf"
        session["user_id"] = 7
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO users (id, name, phone, password_hash, role)"
                " VALUES (7, 'بدون ویترین', '09121119999', 'hash', 'seller')"
            )

    response = _order(client, package_id="blue_tick_30d")

    assert response.status_code == 409
    assert response.get_json()["error"] == "store_required"
