"""Regression tests for image cleanup on listing delete and full store profile updates."""
from io import BytesIO

import main as app_module


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


def test_delete_listing_removes_image_file_from_disk(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    upload_folder = tmp_path / "uploads"
    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", upload_folder)
    app_module.app.config["UPLOAD_FOLDER"] = str(upload_folder)

    png = b"\x89PNG\r\n\x1a\n" + b"delete-me-image"
    created = client.post(
        "/api/listings",
        data={
            "title": "کالای دارای تصویر",
            "category": "home",
            "city": "تبریز",
            "price": "500000",
            "description": "حذف با تصویر",
            "image": (BytesIO(png), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    item = created.get_json()["item"]
    listing_id = item["id"]
    filename = item["image_path"].rsplit("/", 1)[-1]
    saved = upload_folder / filename
    assert saved.is_file()
    assert saved.read_bytes() == png

    deleted = client.delete(f"/api/listings/{listing_id}", headers={"X-CSRF-Token": "test-token"})
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    assert not saved.exists()

    missing = client.get(f"/api/listings/{listing_id}")
    assert missing.status_code == 404


def test_delete_listing_without_image_still_succeeds(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    created = client.post(
        "/api/listings",
        json={"title": "بدون تصویر", "category": "home", "city": "تهران", "price": 1000},
    )
    assert created.status_code == 201
    listing_id = created.get_json()["item"]["id"]
    deleted = client.delete(f"/api/listings/{listing_id}", headers={"X-CSRF-Token": "test-token"})
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True


def test_store_owner_can_update_extended_profile_fields(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/my/store").get_json()["item"]["id"]
    response = client.patch(
        f"/api/stores/{store_id}",
        headers={"X-CSRF-Token": "test-token"},
        json={
            "name": "ویترین کامل",
            "city": "اصفهان",
            "description": "توضیح به‌روز",
            "category": "digital",
            "contact_name": "علی فروشنده",
            "address": "خیابان اصلی، پلاک ۱۲",
            "hours": "۹ تا ۱۸",
            "in_person": True,
        },
    )
    assert response.status_code == 200, response.get_json()
    item = response.get_json()["item"]
    assert item["name"] == "ویترین کامل"
    assert item["city"] == "اصفهان"
    assert item["description"] == "توضیح به‌روز"
    assert item["category"] == "digital"
    assert item["contact_name"] == "علی فروشنده"
    assert item["address"] == "خیابان اصلی، پلاک ۱۲"
    assert item["hours"] == "۹ تا ۱۸"
    assert item["in_person"] in (1, True)


def test_store_update_rejects_unknown_fields(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    store_id = client.get("/api/my/store").get_json()["item"]["id"]
    response = client.patch(
        f"/api/stores/{store_id}",
        headers={"X-CSRF-Token": "test-token"},
        json={"name": "نام", "owner_id": 99},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_payload"


def test_become_seller_reports_existing_storefront(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        connection.execute("UPDATE users SET role = 'buyer' WHERE id = 1")
    response = client.post("/api/auth/become-seller", headers={"X-CSRF-Token": "test-token"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["role"] == "seller"
    assert data["has_store"] is True
    assert data.get("next") is None


def test_become_seller_prompts_store_creation_when_missing(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as connection:
        connection.execute("DELETE FROM stores WHERE owner_id = 1")
        connection.execute("UPDATE users SET role = 'buyer' WHERE id = 1")
    response = client.post("/api/auth/become-seller", headers={"X-CSRF-Token": "test-token"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["role"] == "seller"
    assert data["has_store"] is False
    assert data["next"] == "/api/stores"
    assert "ویترین" in data["message"]


def test_nearby_search_uses_bounding_box_and_excludes_null_coords(monkeypatch, tmp_path):
    client = setup_test_database(monkeypatch, tmp_path)
    with app_module.get_connection() as db:
        db.execute(
            "UPDATE listings SET latitude=?, longitude=? WHERE title=?",
            (35.6892, 51.3890, "گوشی سامسونگ تمیز و سالم"),
        )
        db.execute(
            "UPDATE listings SET latitude=NULL, longitude=NULL WHERE title=?",
            ("میز کار چوبی مینیمال",),
        )
        # Far away listing should be outside the bounding box for a tight radius.
        db.execute(
            "UPDATE listings SET latitude=?, longitude=? WHERE title=?",
            (36.26, 59.61, "هدفون بی‌سیم"),  # roughly Mashhad
        )
    response = client.get("/api/listings?lat=35.69&lon=51.39&radius_km=30")
    assert response.status_code == 200
    data = response.get_json()
    assert data["nearby"] is True
    titles = {item["title"] for item in data["items"]}
    assert "گوشی سامسونگ تمیز و سالم" in titles
    assert "میز کار چوبی مینیمال" not in titles
    assert all(item.get("latitude") is not None for item in data["items"])
