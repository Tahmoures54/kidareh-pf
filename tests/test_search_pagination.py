"""Tests for FTS-backed search and keyset pagination on /api/listings."""
import app as app_module


def setup_test_database(monkeypatch, tmp_path):
    database = tmp_path / "test-kidareh.sqlite3"
    monkeypatch.setattr(app_module, "DATABASE_PATH", database)
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True, TESTING_OTP_CODE=False)
    client = app_module.app.test_client()
    with app_module.get_connection() as connection:
        connection.execute(
            "INSERT INTO users (name, phone, password_hash, role, phone_verified_at) VALUES (?, ?, ?, ?, ?)",
            ("آزمایش", "09120000000", "test-hash", "seller", "2026-10-09T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO stores (owner_id, name, city, description) VALUES (?, ?, ?, ?)",
            (1, "ویترین آزمایش", "تبریز", "فروشگاه تست"),
        )
    with client.session_transaction() as browser_session:
        browser_session["user_id"] = 1
        browser_session["csrf_token"] = "test-token"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-token"
    return client


def test_listings_response_includes_pagination_fields(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/api/listings?limit=2")
    assert response.status_code == 200
    data = response.get_json()
    assert "items" in data
    assert "has_more" in data
    assert "next_before_id" in data
    assert data["count"] == len(data["items"])
    assert data["count"] <= 2


def test_listings_fts_search_finds_seed_title(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/api/listings?q=گوشی")
    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] >= 1
    assert any("گوشی" in item["title"] for item in data["items"])


def test_listings_cursor_before_id_skips_newer_rows(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    first = client.get("/api/listings?limit=3").get_json()
    assert first["items"]
    pivot = first["items"][0]["id"]
    second = client.get(f"/api/listings?limit=50&before_id={pivot}").get_json()
    assert all(item["id"] < pivot for item in second["items"])


def test_fts_table_is_populated_on_initialize(monkeypatch, tmp_path):
    setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        # External-content FTS COUNT(*) mirrors content rows even if the index is empty.
        # Verify the inverted index via fts5vocab (and a Persian MATCH).
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS _test_fts_vocab USING fts5vocab(listings_fts, 'row')"
        )
        term_count = connection.execute("SELECT COUNT(*) FROM _test_fts_vocab").fetchone()[0]
        connection.execute("DROP TABLE IF EXISTS _test_fts_vocab")
        matched = connection.execute(
            "SELECT COUNT(*) FROM listings_fts WHERE listings_fts MATCH ?",
            ('"گوشی"',),
        ).fetchone()[0]
    assert listing_count > 0
    assert term_count > 0
    assert matched >= 1
