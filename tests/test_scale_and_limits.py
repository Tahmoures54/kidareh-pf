"""Scale-oriented behaviour: rate limits, sharded uploads, cached sitemap.

These cover the work done to prepare for hundreds of thousands of stores and
millions of listings, where a missing limit or an unbounded query stops being
a nuisance and becomes an outage.
"""
import time
from io import BytesIO

import pytest

from kidareh import create_app
from kidareh.core import get_connection, initialize_database
from kidareh.services import rate_limits


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KIDAREH_SEED_DEMO_DATA", "0")
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "scale-test-secret",
            "DATABASE_PATH": str(tmp_path / "instance" / "scale.sqlite3"),
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
    """A signed-in seller with a store, used to exercise write limits."""
    with client.session_transaction() as session:
        session["csrf_token"] = "scale-csrf"
        session["user_id"] = 1
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at)"
                " VALUES ('فروشنده', '09121112222', 'hash', 'seller', 'verified')"
            )
            db.execute("INSERT INTO stores (owner_id, name, city) VALUES (1, 'ویترین', 'تهران')")
    return {"user_id": 1, "store_id": 1}


# --- Index self-healing -------------------------------------------------------


def test_stale_index_definitions_are_repaired(app):
    """A renamed-but-changed index must be rebuilt, not silently kept.

    `CREATE INDEX IF NOT EXISTS` is a no-op when the name already exists, so a
    deployment upgraded in place would keep whichever definition it happened to
    have. Comparing definitions is what prevents that.
    """
    from kidareh.core import PERFORMANCE_INDEXES, _ensure_performance_indexes, get_connection

    with app.app_context():
        with get_connection() as db:
            db.execute("DROP INDEX IF EXISTS idx_listings_store_id")
            db.execute("CREATE INDEX idx_listings_store_id ON listings(store_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category)")

            _ensure_performance_indexes(db)

            definitions = {
                row["name"]: row["sql"]
                for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
            }
            assert definitions["idx_listings_store_id"] == PERFORMANCE_INDEXES["idx_listings_store_id"]
            assert "idx_listings_category" not in definitions  # superseded, dropped


def test_index_ensuring_is_idempotent(app):
    """Running it twice must not rebuild anything (no start-up churn)."""
    from kidareh.core import _ensure_performance_indexes, get_connection

    with app.app_context():
        with get_connection() as db:
            _ensure_performance_indexes(db)
            before = {
                row["name"]: row["sql"]
                for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
            }
            _ensure_performance_indexes(db)
            after = {
                row["name"]: row["sql"]
                for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
            }
    assert before == after


# --- Rate limits --------------------------------------------------------------


def test_rate_limiter_allows_up_to_the_limit_then_blocks(app, seller):
    with app.app_context():
        for _ in range(3):
            remaining = rate_limits.consume("unit_test", "caller-1", limit=3, window_seconds=60)
        assert remaining == 0
        with pytest.raises(rate_limits.RateLimitExceeded) as raised:
            rate_limits.consume("unit_test", "caller-1", limit=3, window_seconds=60)
    assert raised.value.retry_after >= 1


def test_rate_limiter_scopes_are_independent(app):
    with app.app_context():
        rate_limits.consume("scope_a", "caller", limit=1, window_seconds=60)
        # A different scope (or a different caller) has its own budget.
        assert rate_limits.consume("scope_b", "caller", limit=1, window_seconds=60) == 0
        assert rate_limits.consume("scope_a", "other-caller", limit=1, window_seconds=60) == 0


def test_rate_limiter_window_rolls_over(app, monkeypatch):
    clock = {"now": time.time()}
    monkeypatch.setattr(rate_limits.time, "time", lambda: clock["now"])
    with app.app_context():
        rate_limits.consume("rolling", "caller", limit=1, window_seconds=60)
        with pytest.raises(rate_limits.RateLimitExceeded):
            rate_limits.consume("rolling", "caller", limit=1, window_seconds=60)
        clock["now"] += 61
        assert rate_limits.consume("rolling", "caller", limit=1, window_seconds=60) == 0


def test_rate_limiter_hashes_the_key(app):
    with app.app_context():
        rate_limits.consume("hashing", "09123456789", limit=5, window_seconds=60)
        with get_connection() as db:
            stored = db.execute("SELECT key_hash FROM rate_limits WHERE scope='hashing'").fetchone()
    # Raw phone numbers and IPs must never be persisted.
    assert "09123456789" not in stored["key_hash"]


def test_listing_creation_is_rate_limited(client, seller):
    payload = {
        "title": "کالای تکراری",
        "category": "home",
        "city": "تهران",
        "price": 1000,
        "description": "تست محدودیت",
    }
    blocked = None
    for index in range(65):
        response = client.post(
            "/api/listings",
            headers={"X-CSRF-Token": "scale-csrf"},
            json={**payload, "title": f"کالا {index}"},
        )
        if response.status_code == 429:
            blocked = response
            break
    assert blocked is not None
    body = blocked.get_json()
    assert body["error"] == "listing_create"
    assert body["retry_after"] >= 1


def test_store_creation_is_rate_limited(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "scale-csrf"
        session["user_id"] = 9
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO users (id, name, phone, password_hash, role)"
                " VALUES (9, 'فروشنده', '09121119999', 'hash', 'seller')"
            )
    responses = [
        client.post(
            "/api/stores",
            headers={"X-CSRF-Token": "scale-csrf"},
            json={"name": f"ویترین {index}", "city": "تهران"},
        )
        for index in range(7)
    ]
    assert responses[0].status_code == 201
    assert any(response.status_code == 429 for response in responses[1:])


def test_reporting_is_rate_limited(client, seller):
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO listings (title, category, city, price) VALUES ('کالا', 'home', 'تهران', 1000)"
            )
    responses = [
        client.post(
            "/api/reports",
            headers={"X-CSRF-Token": "scale-csrf"},
            json={"target_type": "listing", "target_id": 1, "reason": "spam", "details": "تست"},
        )
        for _ in range(12)
    ]
    assert responses[0].status_code == 201
    assert any(response.status_code == 429 for response in responses[-3:])


def test_chat_messages_are_rate_limited(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "scale-csrf"
        session["user_id"] = 1
    with client.application.app_context():
        with get_connection() as db:
            db.execute(
                "INSERT INTO users (id, name, phone, password_hash, role)"
                " VALUES (1, 'خریدار', '09121111111', 'hash', 'buyer')"
            )
            db.execute(
                "INSERT INTO users (id, name, phone, password_hash, role)"
                " VALUES (2, 'فروشنده', '09121112222', 'hash', 'seller')"
            )
            db.execute("INSERT INTO stores (owner_id, name, city) VALUES (2, 'ویترین', 'تهران')")
            db.execute(
                "INSERT INTO listings (title, category, city, price, owner_id, store_id)"
                " VALUES ('کالا', 'home', 'تهران', 1000, 2, 1)"
            )
            db.execute(
                "INSERT INTO conversations (id, listing_id, buyer_id, seller_id) VALUES (1, 1, 1, 2)"
            )
    # The cooldown alone stops rapid-fire messages.
    first = client.post(
        "/api/conversations/1/messages",
        headers={"X-CSRF-Token": "scale-csrf"},
        json={"body": "سلام"},
    )
    second = client.post(
        "/api/conversations/1/messages",
        headers={"X-CSRF-Token": "scale-csrf"},
        json={"body": "سلام دوباره"},
    )
    assert first.status_code == 201
    assert second.status_code == 429


# --- Upload sharding ----------------------------------------------------------


def test_uploaded_images_are_stored_in_sharded_directories(client, seller):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    response = client.post(
        "/api/listings",
        headers={"X-CSRF-Token": "scale-csrf"},
        data={
            "title": "کالا با تصویر",
            "category": "home",
            "city": "تهران",
            "price": "1000",
            "image": (BytesIO(png), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    image_path = response.get_json()["item"]["image_path"]

    prefix, shard, filename = image_path.split("/")[-3:]
    assert prefix == "uploads"
    assert len(shard) == 2
    assert filename.startswith(shard)

    from pathlib import Path

    upload_folder = Path(client.application.config["UPLOAD_FOLDER"])
    assert (upload_folder / shard / filename).is_file()


def test_deleting_a_listing_removes_the_sharded_image(client, seller):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    created = client.post(
        "/api/listings",
        headers={"X-CSRF-Token": "scale-csrf"},
        data={
            "title": "کالا با تصویر",
            "category": "home",
            "city": "تهران",
            "price": "1000",
            "image": (BytesIO(png), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    listing_id = created.get_json()["item"]["id"]
    relative = created.get_json()["item"]["image_path"].replace("/static/uploads/", "", 1)
    from pathlib import Path

    saved = Path(client.application.config["UPLOAD_FOLDER"]) / relative
    assert saved.is_file()

    deleted = client.delete(f"/api/listings/{listing_id}", headers={"X-CSRF-Token": "scale-csrf"})
    assert deleted.status_code == 200
    assert not saved.exists()


def test_upload_route_refuses_path_traversal(client):
    for path in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "ab/../../secret.txt"):
        response = client.get(f"/static/uploads/{path}")
        assert response.status_code in (404, 400), path


# --- Sitemap caching ----------------------------------------------------------


def test_sitemap_is_cached_then_refreshes(client, monkeypatch):
    """Crawlers must be served without re-querying, but new pages must appear."""
    from kidareh.routes import pages

    pages._sitemap_cache.clear()

    first = client.get("/sitemap.xml")
    assert first.status_code == 200
    assert "max-age=600" in first.headers["Cache-Control"]
    first_body = first.get_data()

    with client.application.app_context():
        with get_connection() as db:
            db.execute("INSERT INTO stores (name, city) VALUES ('ویترین تازه', 'تهران')")

    # Still cached: the brand-new store is not in the response yet.
    assert client.get("/sitemap.xml").get_data() == first_body

    # Once the cache is stale the document is rebuilt and picks the store up.
    monkeypatch.setattr(pages, "SITEMAP_CACHE_SECONDS", 0)
    refreshed = client.get("/sitemap.xml").get_data()
    assert refreshed != first_body
    assert "/store/1" in refreshed.decode("utf-8")


def test_robots_txt_is_cacheable(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "max-age=3600" in response.headers["Cache-Control"]
    assert "Sitemap:" in response.get_data(as_text=True)
