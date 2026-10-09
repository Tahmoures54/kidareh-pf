import app as app_module


def setup_test_database(monkeypatch, tmp_path):
    database = tmp_path / "test-kidareh.sqlite3"
    monkeypatch.setattr(app_module, "DATABASE_PATH", database)
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()
    with app_module.get_connection() as connection:
        connection.execute(
            "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
            ("آزمایش", "09120000000", "test-hash", "seller"),
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


def test_homepage_renders_persian_marketplace(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "کی‌داره".encode() in response.data
    assert b"listingGrid" in response.data


def test_health_endpoint():
    response = app_module.app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_listing_api_returns_seed_data(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/api/listings")
    data = response.get_json()
    assert response.status_code == 200
    assert data["count"] >= 1
    assert any(item["title"] == "گوشی سامسونگ تمیز و سالم" for item in data["items"])


def test_listing_api_filters_by_category(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/api/listings?category=digital")
    data = response.get_json()
    assert response.status_code == 200
    assert data["items"]
    assert all(item["category"] == "digital" for item in data["items"])


def test_listing_api_search_is_applied(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.get("/api/listings?q=گوشی")
    data = response.get_json()
    assert response.status_code == 200
    assert data["count"] == 1
    assert "گوشی" in data["items"][0]["title"]

def test_listing_detail_returns_matching_item(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    listing = client.get("/api/listings").get_json()["items"][0]

    response = client.get(f"/api/listings/{listing['id']}")

    assert response.status_code == 200
    assert response.get_json()["item"]["id"] == listing["id"]
    assert response.get_json()["item"]["title"] == listing["title"]


def test_listing_detail_returns_json_404_for_missing_item(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)

    response = client.get("/api/listings/999999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "listing_not_found"}

def test_create_listing_returns_created_item(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    payload = {
        "title": "میز مطالعه",
        "category": "home",
        "city": "تبریز",
        "price": 1250000,
        "description": "میز سالم و تمیز",
    }

    response = client.post("/api/listings", json=payload)

    assert response.status_code == 201
    item = response.get_json()["item"]
    assert item["title"] == payload["title"]
    assert item["category"] == payload["category"]
    assert item["price"] == payload["price"]
    assert item["featured"] is False


def test_create_listing_rejects_invalid_category(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    payload = {
        "title": "آگهی نامعتبر",
        "category": "unknown",
        "city": "تهران",
        "price": 1000,
        "description": "",
    }

    response = client.post("/api/listings", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_category"


def test_create_listing_rejects_negative_price(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    payload = {
        "title": "آگهی تست",
        "category": "home",
        "city": "تهران",
        "price": -10,
        "description": "",
    }

    response = client.post("/api/listings", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_price"


def test_create_listing_with_valid_png_upload(monkeypatch, tmp_path):
    from io import BytesIO

    client = setup_test_database(monkeypatch, tmp_path)
    upload_folder = tmp_path / "uploads"
    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload_folder)
    app_module.app.config["UPLOAD_FOLDER"] = str(upload_folder)
    png = b"\x89PNG\r\n\x1a\n" + b"test-image-data"
    response = client.post("/api/listings", data={"title": "صندلی سالم", "category": "home", "city": "تبریز", "price": "850000", "description": "بازدید حضوری", "image": (BytesIO(png), "my-photo.png")}, content_type="multipart/form-data")
    assert response.status_code == 201
    item = response.get_json()["item"]
    assert item["image_path"].startswith("/static/uploads/")
    saved_file = upload_folder / item["image_path"].rsplit("/", 1)[-1]
    assert saved_file.read_bytes() == png


def test_create_listing_rejects_non_image_upload(monkeypatch, tmp_path):
    from io import BytesIO

    client = setup_test_database(monkeypatch, tmp_path)
    response = client.post("/api/listings", data={"title": "آگهی با فایل نامعتبر", "category": "home", "city": "تهران", "price": "1000", "description": "", "image": (BytesIO(b"this is not an image"), "photo.jpg")}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_image"


def test_create_listing_without_image_keeps_empty_image_path(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.post("/api/listings", json={"title": "آگهی ساده", "category": "home", "city": "تهران", "price": 0})
    assert response.status_code == 201
    assert response.get_json()["item"]["image_path"] == ""


def test_create_listing_normalizes_persian_seller_phone(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.post(
        "/api/listings",
        json={
            "title": "میز برای بازدید حضوری",
            "category": "home",
            "city": "تبریز",
            "price": 900000,
            "seller_phone": "۰۹۱۲ ۳۴۵ ۶۷۸۹",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["item"]["seller_phone"] == "09123456789"


def test_create_listing_rejects_invalid_seller_phone(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    response = client.post(
        "/api/listings",
        json={
            "title": "آگهی با شماره نامعتبر",
            "category": "home",
            "city": "تهران",
            "price": 1000,
            "seller_phone": "12345",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_seller_phone"


def test_listing_detail_includes_seller_phone(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    created = client.post(
        "/api/listings",
        json={
            "title": "میز با امکان بازدید",
            "category": "home",
            "city": "تبریز",
            "price": 900000,
            "seller_phone": "09123456789",
        },
    )
    listing_id = created.get_json()["item"]["id"]

    response = client.get(f"/api/listings/{listing_id}")

    assert response.status_code == 200
    assert response.get_json()["item"]["seller_phone"] == "09123456789"


def test_listing_creation_requires_login_and_csrf(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with client.session_transaction() as browser_session:
        browser_session.clear()
    response = client.post(
        "/api/listings",
        json={"title": "آگهی", "category": "home", "city": "تهران", "price": 0},
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_signup_creates_account_and_hashes_password(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with client.session_transaction() as browser_session:
        browser_session.clear()
        browser_session["csrf_token"] = "test-token"
    response = client.post(
        "/api/auth/signup",
        headers={"X-CSRF-Token": "test-token"},
        json={"name": "کاربر جدید", "phone": "۰۹۱۲۳۴۵۶۷۸۹", "password": "secure-pass-123"},
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["phone"] == "09123456789"
    with app_module.get_connection() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE phone = ?", ("09123456789",)).fetchone()
    assert row["password_hash"] != "secure-pass-123"


def test_only_owner_can_edit_or_delete_listing(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    created = client.post(
        "/api/listings",
        json={"title": "میز خودم", "category": "home", "city": "تبریز", "price": 1000},
    )
    listing_id = created.get_json()["item"]["id"]
    with app_module.get_connection() as connection:
        connection.execute(
            "INSERT INTO users (name, phone, password_hash) VALUES (?, ?, ?)",
            ("کاربر دوم", "09120000001", "test-hash"),
        )
    with client.session_transaction() as browser_session:
        browser_session["user_id"] = 2
    denied = client.patch(
        f"/api/listings/{listing_id}",
        json={"title": "تغییر غیرمجاز"},
    )
    assert denied.status_code == 403
    denied_delete = client.delete(f"/api/listings/{listing_id}")
    assert denied_delete.status_code == 403
    with client.session_transaction() as browser_session:
        browser_session["user_id"] = 1
    updated = client.patch(
        f"/api/listings/{listing_id}",
        json={"title": "میز ویرایش‌شده"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["item"]["title"] == "میز ویرایش‌شده"
    deleted = client.delete(f"/api/listings/{listing_id}")
    assert deleted.status_code == 200


def test_guest_can_browse_storefronts_and_store_products(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with client.session_transaction() as browser_session:
        browser_session.clear()
    stores = client.get("/api/stores")
    assert stores.status_code == 200
    assert stores.get_json()["items"]
    store_id = stores.get_json()["items"][0]["id"]
    detail = client.get(f"/api/stores/{store_id}")
    assert detail.status_code == 200
    assert "store" in detail.get_json()
    assert "items" in detail.get_json()


def test_following_store_requires_login_and_csrf(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/stores").get_json()["items"][0]["id"]
    with client.session_transaction() as browser_session:
        browser_session.clear()
    denied = client.post(f"/api/stores/{store_id}/follow")
    assert denied.status_code == 401

    with client.session_transaction() as browser_session:
        browser_session["user_id"] = 1
        browser_session["csrf_token"] = "test-token"
    followed = client.post(f"/api/stores/{store_id}/follow", headers={"X-CSRF-Token": "test-token"})
    assert followed.status_code == 200
    assert followed.get_json()["following"] is True
    unfollowed = client.post(f"/api/stores/{store_id}/follow", headers={"X-CSRF-Token": "test-token"})
    assert unfollowed.status_code == 200
    assert unfollowed.get_json()["following"] is False


def test_saved_product_requires_login(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    product_id = client.get("/api/listings").get_json()["items"][0]["id"]
    with client.session_transaction() as browser_session:
        browser_session.clear()
    response = client.post(f"/api/listings/{product_id}/save")
    assert response.status_code == 401


def test_buyer_cannot_create_store(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        connection.execute("UPDATE users SET role = 'buyer' WHERE id = 1")
    response = client.post(
        "/api/stores",
        headers={"X-CSRF-Token": "test-token"},
        json={"name": "ویترین خریدار", "city": "تهران", "description": ""},
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "seller_account_required"


def test_buyer_can_switch_to_seller_when_ready_to_open_storefront(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        connection.execute("UPDATE users SET role = 'buyer' WHERE id = 1")
    response = client.post("/api/auth/become-seller", headers={"X-CSRF-Token": "test-token"})
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "seller"


def test_store_owner_can_update_store_details(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/my/store").get_json()["item"]["id"]
    response = client.patch(f"/api/stores/{store_id}", headers={"X-CSRF-Token": "test-token"}, json={"name": "ویترین تازه", "city": "تهران", "description": "توضیح جدید"})
    assert response.status_code == 200
    assert response.get_json()["item"]["name"] == "ویترین تازه"
    assert response.get_json()["item"]["city"] == "تهران"


def test_non_owner_cannot_update_store_details(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        connection.execute("INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)", ("کاربر دیگر", "09120000002", "test-hash", "seller"))
    with client.session_transaction() as browser_session:
        browser_session["user_id"] = 2
    response = client.patch("/api/stores/1", headers={"X-CSRF-Token": "test-token"}, json={"name": "تغییر غیرمجاز"})
    assert response.status_code == 403
    assert response.get_json()["error"] == "store_forbidden"


def test_store_update_rejects_invalid_name(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/my/store").get_json()["item"]["id"]
    response = client.patch(f"/api/stores/{store_id}", headers={"X-CSRF-Token": "test-token"}, json={"name": " "})
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_store_name"


def test_saved_products_api_toggles_and_lists_saved_item(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    product_id = client.get("/api/listings").get_json()["items"][0]["id"]
    saved = client.post(f"/api/listings/{product_id}/save", headers={"X-CSRF-Token": "test-token"})
    assert saved.status_code == 200
    assert saved.get_json()["saved"] is True
    listing = client.get("/api/products/saved")
    assert listing.status_code == 200
    assert any(item["id"] == product_id for item in listing.get_json()["items"])
    removed = client.post(f"/api/listings/{product_id}/save", headers={"X-CSRF-Token": "test-token"})
    assert removed.status_code == 200
    assert removed.get_json()["saved"] is False
    assert all(item["id"] != product_id for item in client.get("/api/products/saved").get_json()["items"])


def test_following_stores_api_lists_followed_store(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/my/store").get_json()["item"]["id"]
    followed = client.post(f"/api/stores/{store_id}/follow", headers={"X-CSRF-Token": "test-token"})
    assert followed.status_code == 200
    assert followed.get_json()["following"] is True
    response = client.get("/api/stores/following")
    assert response.status_code == 200
    assert any(item["id"] == store_id for item in response.get_json()["items"])
