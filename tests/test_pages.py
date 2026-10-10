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
    assert html.index('id="activeMarketCity"') < html.index('id="promoBanner"')
    assert 'id="citySelect"' in html
    assert 'value="تهران"' in html
    assert 'id="marketListingsTitle">بازار تهران</h2>' in html
    assert 'id="citySelect"' not in html[html.index('id="searchForm"'):html.index('</form>', html.index('id="searchForm"'))]
    assert "کالاها و خدمات معرفی‌شده" not in html
    assert 'id="categorySelect"' in html
    assert 'id="findMyLocationButton"' in html
    assert 'id="nearbyListingsButton"' in html
    assert 'class="category-grid"' not in html
    assert "شهر بازار را خودتان انتخاب می‌کنید؛ مکان‌یابی فقط با درخواست شما انجام می‌شود" in html


def test_homepage_geolocation_is_click_driven_and_uses_api_longitude_parameter():
    from pathlib import Path

    script = Path(app_module.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'findMyLocationButton?.addEventListener("click"' in script
    assert 'nearbyListingsButton?.addEventListener("click"' in script
    assert 'params.set("lon", String(userCoords.lng))' in script
    assert "getCurrentPosition(" in script
    assert 'searchForm.insertAdjacentElement("afterend", nearbyButton)' not in script


def test_market_city_title_tracks_selected_city_and_defaults_to_tehran():
    from pathlib import Path

    script = Path(app_module.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'const city = citySelect?.value.trim() || "تهران"' in script
    assert 'marketListingsTitle.textContent = "بازار " + city' in script
    assert 'localStorage.getItem("kidareh.marketCity")' in script



def test_city_combobox_uses_full_location_api_and_starts_with_popular_cities(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "location-combobox.sqlite3")
    app_module.initialize_database()
    client = app_module.app.test_client()

    popular = client.get("/api/locations")
    assert popular.status_code == 200
    popular_data = popular.get_json()
    assert "تهران" in [item["name"] for item in popular_data["items"]]
    assert all(item["type"] == "city" for item in popular_data["items"])

    searched = client.get("/api/locations?kind=city&q=تهران")
    assert searched.status_code == 200
    assert any(item["name"] == "تهران" for item in searched.get_json()["items"])
    assert all(item["type"] == "city" for item in searched.get_json()["items"])

    # The default location lookup must never mix in villages or unrelated rural records.
    default_search = client.get("/api/locations?q=کارخانه").get_json()["items"]
    assert default_search == []
    assert all(item["type"] == "city" for item in default_search)
    village_search = client.get("/api/locations?kind=village&q=تهران").get_json()["items"]
    assert all(item["type"] == "village" for item in village_search)

    html = client.get("/").get_data(as_text=True)
    assert 'id="marketCityOptions" role="listbox"' in html
    assert 'id="toggleMarketCityPicker"' in html
    assert 'aria-controls="marketCityOptions"' in html
    assert 'id="citySelect" list=' not in html
    register_html = client.get("/register").get_data(as_text=True)
    assert 'id="buyerCity" name="city"' in register_html
    assert 'id="storeCity" name="store_city"' in register_html
    assert 'list="registerCityOptions" data-iran-location' in register_html



def test_category_options_are_shared_across_home_search_seller_and_registration(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "shared-categories.sqlite3")
    app_module.initialize_database()
    client = app_module.app.test_client()

    pages = {
        "/": ('id="categorySelect"', "مواد غذایی، خواربار و خشکبار", "everyday_goods"),
        "/search": ('id="pageCategory"', "مواد غذایی، خواربار و خشکبار", "everyday_goods"),
        "/seller": ('name="category"', "مواد غذایی، خواربار و خشکبار", "everyday_goods"),
        "/register": ('id="storeCategory"', "مواد غذایی، خواربار و خشکبار", "everyday_goods"),
    }
    for path, markers in pages.items():
        response = client.get(path)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, path
        assert all(marker in html for marker in markers), path
        assert 'value="food"' in html, path
        assert 'value="fresh_produce"' in html, path


def test_homepage_uses_compact_accessible_message_ticker_instead_of_large_promo_carousel(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DATABASE_PATH", tmp_path / "compact-ticker.sqlite3")
    app_module.initialize_database()
    response = app_module.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="marketTicker"' in html
    assert 'id="marketTickerMessage" aria-live="polite"' in html
    assert 'id="marketTickerLink"' in html
    assert html.index('id="marketTicker"') < html.index('class="market-location-bar"')
    assert 'id="promoBanner"' not in html
    assert 'class="promo-banner-slide"' not in html

    from pathlib import Path
    script = Path(app_module.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "initMarketTicker" in script
    assert "setInterval(() => show(index + 1), 5000)" in script
    assert 'prefers-reduced-motion: reduce' in script
    assert 'root.addEventListener("mouseenter", stop)' in script
