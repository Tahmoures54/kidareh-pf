import uuid

import app as app_module


def test_dedicated_marketplace_pages_render(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "pages.sqlite3")
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()

    cases = [
        ("/search", "جست‌وجوی کالا"),
        ("/stores", "ویترین فروشگاه‌ها"),
        ("/seller", "فروشگاهت را بچین"),
        ("/account", "حساب کاربری"),
        ("/saved", "محصولات ذخیره‌شده"),
        ("/following", "فروشگاه‌های دنبال‌شده"),
    ]
    for path, expected in cases:
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected.encode() in response.data, path
        assert b"templates" not in response.data


def test_product_and_store_pages_include_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "detail-pages.sqlite3")
    app_module.initialize_database()
    client = app_module.app.test_client()

    with app_module.get_connection() as connection:
        listing = connection.execute("SELECT id FROM listings ORDER BY id LIMIT 1").fetchone()
        store = connection.execute("SELECT id FROM stores ORDER BY id LIMIT 1").fetchone()

    product_response = client.get(f"/product/{listing['id']}")
    store_response = client.get(f"/store/{store['id']}")

    assert product_response.status_code == 200
    assert b"product-detail" in product_response.data
    assert store_response.status_code == 200
    assert b"store-detail" in store_response.data


def test_search_page_preserves_filters(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "search-page.sqlite3")
    app_module.initialize_database()
    response = app_module.app.test_client().get("/search?q=%DA%AF%D9%88%D8%B4%DB%8C&category=digital&city=%D8%AA%D9%87%D8%B1%D8%A7%D9%86")
    assert response.status_code == 200
    assert "گوشی".encode() in response.data
    assert b"digital" in response.data
    assert "تهران".encode() in response.data
