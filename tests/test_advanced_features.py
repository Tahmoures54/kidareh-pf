"""Integration coverage for advanced listing filters, notifications and seller stats."""
import main as app_module


def setup_client(monkeypatch, tmp_path, phone="09120000000", role="seller"):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "advanced-features.sqlite3")
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()
    with app_module.get_connection() as db:
        db.execute(
            "INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
            ("فروشنده", phone, "x", role, "verified"),
        )
        db.execute(
            "INSERT INTO stores(owner_id,name,city,description) VALUES(1,?,?,?)",
            ("فروشگاه تست", "تهران", "توضیح"),
        )
        db.execute(
            "INSERT INTO listings(title,category,city,price,owner_id,store_id) VALUES(?,?,?,?,?,?)",
            ("کالای تهران", "home", "تهران", 1000, 1, 1),
        )
        db.execute(
            "INSERT INTO listings(title,category,city,price,owner_id,store_id) VALUES(?,?,?,?,?,?)",
            ("کالای تبریز", "home", "تبریز", 2000, 1, 1),
        )
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["csrf_token"] = "test-token"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-token"
    return client


def test_listing_filters_accept_province_and_category(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    response = client.get("/api/listings?province=تهران&category=home&limit=20")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items
    assert all(item["city"] == "تهران" for item in items)


def test_new_message_creates_private_notification(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    with app_module.get_connection() as db:
        db.execute(
            "INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
            ("خریدار", "09120000001", "x", "buyer", "verified"),
        )
        listing_id = db.execute("SELECT id FROM listings WHERE title='کالای تهران'").fetchone()[0]
    with client.session_transaction() as session:
        session["user_id"] = 2
    started = client.post("/api/conversations", json={"listing_id": listing_id})
    assert started.status_code == 201
    sent = client.post(
        f"/api/conversations/{started.get_json()['id']}/messages",
        json={"body": "سلام، کالا موجود است؟"},
    )
    assert sent.status_code == 201
    with client.session_transaction() as session:
        session["user_id"] = 1
    response = client.get("/api/notifications")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["unread_count"] >= 1
    assert payload["items"][0]["kind"] == "new_message"


def test_seller_stats_are_scoped_to_current_user(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    response = client.get("/api/seller/stats")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["listing_count"] == 2
    assert payload["views"] >= 0
    assert payload["sales"] >= 0
