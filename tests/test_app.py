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
