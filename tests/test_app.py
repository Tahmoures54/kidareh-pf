import app as app_module


def setup_test_database(monkeypatch, tmp_path):
    database = tmp_path / "test-kidareh.sqlite3"
    monkeypatch.setattr(app_module, "DATABASE_PATH", database)
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


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
    png = b"\\x89PNG\\r\\n\\x1a\\n" + b"test-image-data"
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
