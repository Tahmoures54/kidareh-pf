import app as app_module


def setup_client(monkeypatch, tmp_path, phone="09120000000", role="seller"):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "community.sqlite3")
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()
    with app_module.get_connection() as db:
        db.execute("INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
                   ("کاربر تست", phone, "x", role, "2026-10-09T00:00:00+00:00"))
        db.execute("INSERT INTO stores(owner_id,name,city,description) VALUES(1,?,?,?)",
                   ("فروشگاه تست", "تبریز", "توضیح"))
        db.execute("INSERT INTO listings(title,category,city,price,owner_id,store_id) VALUES(?,?,?,?,?,?)",
                   ("کالای تست", "home", "تبریز", 1000, 1, 1))
    with client.session_transaction() as s:
        s["user_id"] = 1
        s["csrf_token"] = "test-token"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-token"
    return client


def test_buyer_can_start_conversation_and_exchange_messages(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    with app_module.get_connection() as db:
        db.execute("INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
                   ("خریدار", "09120000001", "x", "buyer", "verified"))
        listing_id = db.execute("SELECT id FROM listings WHERE title='کالای تست'").fetchone()[0]
    with client.session_transaction() as s:
        s["user_id"] = 2
    started = client.post("/api/conversations", json={"listing_id": listing_id})
    assert started.status_code == 201
    thread_id = started.get_json()["id"]
    sent = client.post(f"/api/conversations/{thread_id}/messages", json={"body": "سلام، کالا موجود است؟"})
    assert sent.status_code == 201
    got = client.get(f"/api/conversations/{thread_id}/messages")
    assert got.status_code == 200
    assert got.get_json()["items"][0]["body"] == "سلام، کالا موجود است؟"


def test_conversation_is_private_to_participants(monkeypatch, tmp_path):
    client = setup_client(monkeypatch, tmp_path)
    from kidareh.routes.communications import ensure_tables
    ensure_tables()
    with app_module.get_connection() as db:
        db.execute("INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
                   ("خریدار", "09120000001", "x", "buyer", "verified"))
        db.execute("INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
                   ("غریبه", "09120000002", "x", "buyer", "verified"))
        listing_id = db.execute("SELECT id FROM listings WHERE title='کالای تست'").fetchone()[0]
        db.execute("INSERT INTO conversations(listing_id,buyer_id,seller_id) VALUES(?,?,?)", (listing_id, 2, 1))
    with client.session_transaction() as s:
        s["user_id"] = 3
    assert client.get("/api/conversations/1/messages").status_code == 404


def test_support_ticket_owner_and_admin_reply(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PHONE", "09120000000")
    client = setup_client(monkeypatch, tmp_path)
    created = client.post("/api/support/tickets", json={"title": "مشکل در کالا", "category": "listing", "body": "در ثبت کالای جدید با مشکل روبه‌رو شده‌ام."})
    assert created.status_code == 201
    ticket_id = created.get_json()["id"]
    reply = client.post(f"/api/support/tickets/{ticket_id}/messages", json={"body": "درخواست شما بررسی می‌شود."})
    assert reply.status_code == 201
    detail = client.get(f"/api/support/tickets/{ticket_id}")
    assert detail.status_code == 200
    assert len(detail.get_json()["items"]) == 2


def test_admin_dashboard_and_user_ban(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PHONE", "09120000000")
    client = setup_client(monkeypatch, tmp_path)
    with app_module.get_connection() as db:
        db.execute("INSERT INTO users(name,phone,password_hash,role,phone_verified_at) VALUES(?,?,?,?,?)",
                   ("کاربر دوم", "09120000001", "x", "buyer", "verified"))
    response = client.get("/api/admin/dashboard")
    assert response.status_code == 200
    assert response.get_json()["counts"]["users"] == 2
    updated = client.patch("/api/admin/users/2", json={"is_banned": True, "reason": "آزمایش"})
    assert updated.status_code == 200
    with app_module.get_connection() as db:
        assert db.execute("SELECT is_banned FROM users WHERE id=2").fetchone()[0] == 1


def test_admin_dashboard_rejects_non_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PHONE", "09999999999")
    client = setup_client(monkeypatch, tmp_path)
    assert client.get("/api/admin/dashboard").status_code == 403
