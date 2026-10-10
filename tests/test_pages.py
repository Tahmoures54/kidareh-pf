import uuid

import main as app_module


def test_dedicated_marketplace_pages_render(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "pages.sqlite3")
    app_module.initialize_database()
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()

    cases = [
        ("/search", "جست‌وجوی کالا"),
        ("/stores", "ویترین فروشگاه‌ها"),
        ("/seller", "پنل مدیریت فروشگاه"),
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


def test_seller_dashboard_has_storefront_first_layout_and_product_actions(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "seller-dashboard.sqlite3")
    app_module.initialize_database()
    response = app_module.app.test_client().get("/seller")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for marker in (
        'class="seller-hero"',
        'class="seller-metrics"',
        'id="storePanel"',
        'id="addProductPanel"',
        'id="pageListings"',
        'id="sellerStoreMetric"',
        'id="sellerProductMetric"',
    ):
        assert marker in html, marker
    assert "seller-dashboard" in html
    assert "min-height:48px" in html



def test_global_header_exposes_logout_controls_for_authenticated_users(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "header-auth.sqlite3")
    app_module.initialize_database()
    response = app_module.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="headerLoginLink"' in html
    assert 'id="headerRegisterLink"' in html
    assert 'id="headerAccountLink"' in html
    assert 'id="headerLogoutButton"' in html


def test_homepage_city_privacy_and_compact_category_controls(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "city-home.sqlite3")
    app_module.initialize_database()
    response = app_module.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="activeMarketCity"' in html
    assert 'id="citySelect"' in html
    assert 'id="categorySelect"' in html
    assert 'id="findMyLocationButton"' in html
    assert 'id="nearbyListingsButton"' in html
    assert 'class="category-grid"' not in html
    assert "موقعیت مکانی فقط پس از انتخاب شما درخواست می‌شود" in html


def test_homepage_geolocation_is_click_driven_and_uses_api_longitude_parameter():
    from pathlib import Path

    script = Path(app_module.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'findMyLocationButton?.addEventListener("click"' in script
    assert 'nearbyListingsButton?.addEventListener("click"' in script
    assert 'params.set("lon", String(userCoords.lng))' in script
    assert "getCurrentPosition(" in script
    assert 'searchForm.insertAdjacentElement("afterend", nearbyButton)' not in script
