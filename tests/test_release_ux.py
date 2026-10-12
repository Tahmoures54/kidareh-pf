"""UX, PWA and SEO release gates for the public launch of کی‌داره."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from kidareh import create_app
from kidareh.core import get_connection, initialize_database

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
NODE = shutil.which("node")


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE_PATH": str(tmp_path / "instance" / "test.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    with application.app_context():
        initialize_database()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


# ---------- Design tokens & typography ----------
def test_design_tokens_and_dark_mode_are_defined_in_style_css():
    css = read("static/css/style.css")
    for token in ("--color-primary", "--color-success", "--color-warning", "--color-danger",
                  "--radius-lg", "--shadow-md", "--space-4", "--text-base", "--weight-bold"):
        assert token in css, token
    assert "@media (prefers-color-scheme: dark)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_theme_overlay_does_not_pin_root_tokens_with_important():
    theme = read("static/css/theme-mh.css")
    assert not re.search(r":root\s*\{[^}]*!important", theme)


def test_font_is_self_hosted_with_font_display_swap():
    css = read("static/css/style.css")
    assert "font-display: swap" in css
    assert "/static/fonts/Vazirmatn-Variable.woff2" in css
    assert (STATIC / "fonts" / "Vazirmatn-Variable.woff2").stat().st_size > 10_000
    assert (STATIC / "fonts" / "OFL.txt").exists()


def test_no_external_font_requests_in_templates(client):
    for path in ("/", "/stores", "/login"):
        html = client.get(path).get_data(as_text=True)
        assert "fonts.googleapis.com" not in html, path
        assert "fonts.gstatic.com" not in html, path


def test_html_is_persian_rtl(client):
    html = client.get("/").get_data(as_text=True)
    assert '<html lang="fa" dir="rtl">' in html


def test_css_uses_logical_properties_instead_of_physical_margins():
    for name in ("static/css/style.css", "static/css/pages.css", "static/css/components.css"):
        css = read(name)
        assert not re.search(r"(?<![\w-])(margin|padding)-(left|right)\s*:", css), name


def test_components_stylesheet_covers_base_components():
    css = read("static/css/components.css")
    for selector in (".button-primary", ".button-secondary", ".button-ghost", ".button-danger",
                     ".input", ".card", ".badge", ".modal", ".toast", ".skeleton", ".empty-state",
                     "@keyframes fadeInUp", "focus-visible"):
        assert selector in css, selector
    assert "min-height: 44px" in css


def test_components_stylesheet_is_loaded_after_theme_overlay(client):
    html = client.get("/").get_data(as_text=True)
    theme = html.index("theme-mh.css")
    components = html.index("components.css")
    assert components > theme


# ---------- Mobile navigation & AIDA home ----------
def test_shared_shell_stylesheet_owns_full_width_footer_and_mobile_navigation(client):
    home = client.get("/").get_data(as_text=True)
    stores = client.get("/stores").get_data(as_text=True)
    css = read("static/css/site-shell.css")
    assert "site-shell.css?v=20261011-shell-v7" in home
    assert "site-shell.css?v=20261011-shell-v7" in stores
    assert ".site-footer" in css
    assert "width: 100% !important;" in css
    assert "linear-gradient(100deg, var(--kidareh-turquoise-dark), var(--kidareh-turquoise))" in css
    assert ".mobile-bottom-nav {\n  position: fixed;" in css
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in css
    assert "@media (min-width: 900px) {\n  .mobile-bottom-nav { display: none !important; }" in css
    assert 'class="site-header"' in home
    assert 'class="site-footer"' in home
    assert 'class="brand-tagline">سوپر اپلیکیشن خرید حضوری</small>' in home
    assert 'class="brand-city" id="activeMarketCity"' in home
    assert 'class="brand-title-row"' in home
    assert '<span class="brand-mark">ک</span>' not in home
    assert '<span class="brand-mark">ک</span>' not in stores
    for path in ("static/css/style.css", "static/css/pages.css", "static/css/components.css", "static/css/theme-mh.css"):
        source = read(path)
        assert ".site-footer" not in source, path
        assert ".mobile-bottom-nav" not in source, path


def test_home_has_single_primary_cta_above_the_fold():
    html = read("templates/index.html")
    hero_start = html.index('<section class="home-intro"')
    hero_end = html.index('<datalist id="iranCityOptions"', hero_start)
    hero = html[hero_start:hero_end]
    assert "منتظر نمون تا مشتری بیاد!" in hero
    assert "ویترینت رو به دلِ خونه‌ها بفرست." in hero
    assert 'href="/seller">ویترینم رو بساز' in hero
    assert 'id="homeRotatingMessage"' not in hero
    assert 'id="homeMessageAction"' not in hero
    assert hero.count("button-primary") == 1
    assert 'class="home-intro-art"' not in hero


# ---------- PWA manifest / icons / shortcuts ----------
def test_manifest_meets_installability_requirements(client):
    manifest = json.loads(client.get("/static/manifest.webmanifest").get_data(as_text=True))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/?utm_source=pwa"
    assert manifest["lang"] == "fa"
    assert manifest["dir"] == "rtl"
    assert manifest["theme_color"] == "#0E7490"
    sizes = {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]}
    assert ("192x192", "maskable") in sizes
    assert ("512x512", "maskable") in sizes
    names = [shortcut["name"] for shortcut in manifest["shortcuts"]]
    assert names == ["جستجو", "ثبت آگهی", "پیام‌ها"]


def test_manifest_icon_files_exist_and_are_png(client):
    manifest = json.loads(client.get("/static/manifest.webmanifest").get_data(as_text=True))
    for icon in manifest["icons"]:
        if icon["src"].endswith(".svg"):
            continue
        path = ROOT / icon["src"].lstrip("/")
        assert path.exists(), icon["src"]
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", icon["src"]


def test_service_worker_precaches_release_assets_and_versions_cache():
    sw = read("static/sw.js")
    assert 'CACHE_VERSION = "v6"' in sw
    for asset in ("/static/offline.html", "/static/css/style.css", "/static/css/theme-mh.css",
                  "/static/css/site-shell.css",
                  "/static/js/app.js", "/static/manifest.webmanifest",
                  "/static/fonts/Vazirmatn-Variable.woff2"):
        assert asset in sw, asset
    assert "skipWaiting" in sw and "clients.claim" in sw
    assert "SKIP_WAITING" in sw
    assert "staleWhileRevalidate" in sw and "networkFirst" in sw


def test_pwa_update_toast_and_install_script_are_wired():
    pwa = read("static/js/pwa.js")
    assert "نسخه‌ی جدید آماده است، بروزرسانی کنم؟" in pwa
    assert "نسخه‌ی جدید نصب شد" in pwa
    assert "beforeinstallprompt" in pwa and "appinstalled" in pwa
    assert "Add to Home Screen" in pwa


def test_offline_page_has_retry_and_cached_pages(client):
    html = client.get("/static/offline.html").get_data(as_text=True)
    assert "تلاش دوباره" in html
    assert "cachedList" in html


# ---------- SEO ----------
def test_robots_txt_points_to_sitemap_and_blocks_private_areas(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Disallow: /api/" in body
    assert "Disallow: /account" in body
    assert "Sitemap: http://localhost/sitemap.xml" in body


def test_sitemap_lists_public_pages_and_dynamic_listings(client, app):
    with app.app_context():
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO listings (title, category, city, price, description) VALUES (?, ?, ?, ?, ?)",
                ("گلدان سفالی", "home", "تهران", 150000, "دست‌ساز"),
            )
            listing_id = cursor.lastrowid
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<loc>http://localhost/search</loc>" in xml
    assert f"<loc>http://localhost/product/{listing_id}</loc>" in xml


def test_product_page_includes_product_json_ld(client, app):
    with app.app_context():
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO listings (title, category, city, price, description) VALUES (?, ?, ?, ?, ?)",
                ("میز چوبی", "home", "اصفهان", 2500000, "چوب گردو"),
            )
            listing_id = cursor.lastrowid
    html = client.get(f"/product/{listing_id}").get_data(as_text=True)
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match, "JSON-LD missing"
    data = json.loads(match.group(1))
    assert data["@type"] == "Product"
    assert data["name"] == "میز چوبی"
    assert data["offers"]["price"] == 2500000
    assert data["offers"]["priceCurrency"] == "IRR"


def test_store_page_includes_local_business_json_ld(client, app):
    from werkzeug.security import generate_password_hash
    with app.app_context():
        with get_connection() as connection:
            user_id = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("مالک", "09120000001", generate_password_hash("x"), "seller"),
            ).lastrowid
            store_id = connection.execute(
                "INSERT INTO stores (owner_id, name, city, description) VALUES (?, ?, ?, ?)",
                (user_id, "فروشگاه نمونه", "شیراز", "صنایع دستی"),
            ).lastrowid
    html = client.get(f"/store/{store_id}").get_data(as_text=True)
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert data["@type"] == "LocalBusiness"
    assert data["address"]["addressLocality"] == "شیراز"


def test_jsonld_is_absent_for_unknown_product(client):
    html = client.get("/product/999999").get_data(as_text=True)
    assert "application/ld+json" not in html


# ---------- Install / onboarding behaviour (pure logic, run with Node when available) ----------
NODE_RULES_TEST = r"""
const r = require(process.argv[2]);
const DAY = 24 * 60 * 60 * 1000;
const out = {
  standaloneBlocks: r.canOfferInstall({ isStandalone: true, dismissedAt: 0, now: 1 }),
  freshAllowed: r.canOfferInstall({ isStandalone: false, dismissedAt: 0, now: 1 }),
  recentDismissBlocks: r.canOfferInstall({ isStandalone: false, dismissedAt: 1000, now: 2000 }),
  oldDismissAllows: r.canOfferInstall({ isStandalone: false, dismissedAt: 1000, now: 1000 + 8 * DAY }),
  timeTrigger: r.isEngagementTriggered({ residenceMs: 15000, scrollRatio: 0, clickedProduct: false }),
  earlyNoTrigger: r.isEngagementTriggered({ residenceMs: 14999, scrollRatio: 0.49, clickedProduct: false }),
  scrollTrigger: r.isEngagementTriggered({ residenceMs: 0, scrollRatio: 0.5, clickedProduct: false }),
  productClickTrigger: r.isEngagementTriggered({ residenceMs: 0, scrollRatio: 0, clickedProduct: true }),
  iosPath: r.installPath({ hasNativePrompt: false, userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)" }),
  nativePath: r.installPath({ hasNativePrompt: true, userAgent: "Mozilla/5.0 (Linux; Android 14)" }),
  androidNoPrompt: r.installPath({ hasNativePrompt: false, userAgent: "Mozilla/5.0 (Linux; Android 14)" })
};
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_install_prompt_rules_follow_product_spec(tmp_path):
    script = tmp_path / "rules-check.js"
    script.write_text(NODE_RULES_TEST, encoding="utf-8")
    result = subprocess.run(
        [NODE, str(script), str(STATIC / "js" / "pwa-rules.js")],
        check=True, capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout)
    assert data == {
        "standaloneBlocks": False,
        "freshAllowed": True,
        "recentDismissBlocks": False,
        "oldDismissAllows": True,
        "timeTrigger": True,
        "earlyNoTrigger": False,
        "scrollTrigger": True,
        "productClickTrigger": True,
        "iosPath": "ios-guide",
        "nativePath": "native",
        "androidNoPrompt": "none",
    }


# ---------- Release hygiene ----------
def test_no_console_log_or_debug_true_in_shipped_code():
    offenders = []
    for path in list(STATIC.rglob("*.js")) + list((ROOT / "kidareh").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "console.log" in text or "debug=True" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_secret_key_is_read_from_environment():
    init = read("kidareh/__init__.py")
    assert 'os.environ.get("SECRET_KEY"' in init


def test_static_cache_headers_split_long_cache_and_revalidation(client):
    font = client.get("/static/fonts/Vazirmatn-Variable.woff2")
    assert font.headers["Cache-Control"] == "public, max-age=604800"
    script = client.get("/static/js/ui.js")
    assert script.headers["Cache-Control"] == "public, max-age=0, must-revalidate"
    assert "ETag" in script.headers or script.get_etag()[0] is not None


def test_user_facing_messages_avoid_generic_error_copy():
    for name in ("static/js/app.js", "static/js/seller.js", "static/js/auth.js", "static/js/auth-pages.js"):
        text = read(name)
        assert "خطایی رخ داد" not in text, name
        assert '"خطا در دریافت کالاها"' not in text, name
    assert "کالا ثبت شد؛ ویترینت آمادهٔ معرفی است" in read("static/js/seller.js")


def test_header_navigation_is_deduplicated_and_auth_actions_have_feedback(client):
    html = client.get("/").get_data(as_text=True)
    css = read("static/css/site-shell.css")
    desktop_start = html.index('<nav class="desktop-nav"')
    desktop_end = html.index('</nav>', desktop_start)
    desktop_nav = html[desktop_start:desktop_end]
    assert '>جست‌وجوی کالا</a>' in desktop_nav
    assert 'href="/stores"' in desktop_nav
    assert 'class="header-search-link"' not in html
    assert 'class="button button-primary" href="/stores"' not in html
    assert desktop_nav.count('href="/search"') == 1
    assert desktop_nav.count('href="/stores"') == 1
    assert 'id="headerLoginLink"' in html
    assert 'id="headerRegisterLink"' in html
    assert "header-auth-button:hover" in css
    assert "header-auth-button:active" in css
    assert "header-auth-button:focus-visible" in css
    assert "prefers-reduced-motion: reduce" in css


def test_legal_links_are_hidden_until_auth_state_is_confirmed_and_store_label_is_clear(client):
    home = client.get("/").get_data(as_text=True)
    stores = client.get("/stores").get_data(as_text=True)
    auth_script = read("static/js/header-auth.js")

    assert 'id="legalLinks"' in home and 'id="legalLinks"' in stores
    assert 'aria-label="پیوندهای حقوقی" hidden' in home
    assert 'aria-label="پیوندهای حقوقی" hidden' in stores
    assert 'setVisible(legalLinks, signedIn)' in auth_script
    assert 'id="headerSellerLink"' in home and "مدیریت فروشگاه" in home
    assert 'id="mobileSellerLink"' in home and "مدیریت فروشگاه" in home
    assert "مدیریت فروشگاه و ویترین آنلاین" in home



def test_seller_dashboard_redirects_guests_to_registration_and_serves_signed_in_users(client, app):
    guest_response = client.get("/seller")
    assert guest_response.status_code == 302
    from urllib.parse import parse_qs, urlsplit
    location = urlsplit(guest_response.headers["Location"])
    assert location.path == "/register"
    assert parse_qs(location.query).get("next") == ["/seller"]

    with app.app_context():
        with get_connection() as connection:
            user_id = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("فروشنده آزمایشی", "09120000002", "test-hash", "seller"),
            ).lastrowid

    with client.session_transaction() as session:
        session["user_id"] = user_id

    signed_in_response = client.get("/seller")
    assert signed_in_response.status_code == 200
    assert "پنل فروشگاه من" in signed_in_response.get_data(as_text=True)


def test_guest_can_browse_catalog_but_private_pages_require_registration(client):
    public_paths = ("/", "/search", "/stores", "/product/1", "/store/1")
    for path in public_paths:
        response = client.get(path)
        assert response.status_code == 200, path

    private_paths = (
        "/seller", "/seller/tags", "/monetization", "/account", "/saved",
        "/following", "/messages", "/support",
    )
    from urllib.parse import parse_qs, urlsplit
    for path in private_paths:
        response = client.get(path)
        assert response.status_code == 302, path
        location = urlsplit(response.headers["Location"])
        assert location.path == "/register", path
        assert parse_qs(location.query).get("next") == [path], path


def test_admin_pages_are_not_public(client, app):
    assert client.get("/admin").status_code == 302
    assert client.get("/admin/reports").status_code == 302

    with app.app_context():
        with get_connection() as connection:
            user_id = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("خریدار آزمایشی", "09120000003", "test-hash", "buyer"),
            ).lastrowid
    with client.session_transaction() as session:
        session["user_id"] = user_id
    assert client.get("/admin").status_code == 403
    assert client.get("/admin/reports").status_code == 403


def test_auth_pages_preserve_requested_seller_destination():
    script = read("static/js/auth-pages.js")
    assert 'query.get("next")' in script
    assert 'window.location.assign(authUrl("/register"))' in script
    assert 'requestedNext || (data.user.role === "seller" ? "/seller" : "/")' in script


def test_home_navigation_omits_redundant_home_links_but_inner_pages_keep_home(client):
    home = client.get("/").get_data(as_text=True)
    stores = client.get("/stores").get_data(as_text=True)

    desktop_start = home.index('<nav class="desktop-nav"')
    desktop_end = home.index('</nav>', desktop_start)
    desktop_nav = home[desktop_start:desktop_end]
    mobile_start = home.index('<nav class="mobile-bottom-nav home-bottom-nav"')
    mobile_end = home.index('</nav>', mobile_start)
    mobile_nav = home[mobile_start:mobile_end]

    assert 'href="/" aria-current="page">خانه</a>' not in desktop_nav
    assert 'href="/" aria-current="page"' not in mobile_nav
    assert 'href="/search"' in desktop_nav and 'href="/stores"' in desktop_nav
    assert 'href="/search"' in mobile_nav and 'href="/stores"' in mobile_nav
    assert 'repeat(3, minmax(0, 1fr))' in read("static/css/site-shell.css")
    assert 'href="/"' in stores


# ---------- Support center: user-facing ticket workflow ----------
def test_support_page_is_a_real_ticket_center_for_signed_in_users(client, app):
    from werkzeug.security import generate_password_hash
    with app.app_context():
        with get_connection() as connection:
            user_id = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                ("کاربر پشتیبانی", "09120000004", generate_password_hash("x"), "buyer"),
            ).lastrowid
    with client.session_transaction() as session:
        session["user_id"] = user_id

    response = client.get("/support")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "پشتیبانی و پیگیری درخواست‌ها" in html
    assert 'id="supportForm"' in html
    assert 'id="supportTicketList"' in html
    assert 'id="supportReplyForm"' in html
    assert "/api/support/tickets" in html
    assert "محصولات ذخیره‌شده" not in html


def test_help_center_distinguishes_faq_from_actual_support(client):
    html = client.get("/help").get_data(as_text=True)
    assert "پاسخ پرسش‌های پرتکرار" in html
    assert "ثبت درخواست پشتیبانی" in html
    assert 'href="/support"' in html
    base = read("templates/base.html")
    assert '<a href="/help">سؤالات رایج</a>' in base
    assert '<a href="/support">پشتیبانی</a>' in base


def test_admin_dashboard_exposes_real_ticket_reply_action():
    script = read("static/js/communications.js")
    assert 'data-reply-ticket="' in script
    assert 'root.querySelectorAll("[data-reply-ticket]")' in script
    assert '"/api/support/tickets/"+b.dataset.replyTicket+"/messages"' in script
    assert 'در حال بررسی' in script



def test_registration_form_uses_vertical_layout_and_mobile_sizing(client):
    html = client.get("/register").get_data(as_text=True)
    css = read("static/css/auth-pages.css")
    assert "auth-pages.css?v=20261011-register-turquoise-header-v2" in html
    assert '.auth-page[data-auth-mode="register"] .auth-role-grid' in css
    assert '.auth-page[data-auth-mode="register"] .auth-field-row' in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert '@media (max-width: 520px)' in css
    assert 'id="continueRoleButton"' not in html
    assert 'radio.addEventListener("change"' in read("static/js/auth-pages.js")
    assert 'if (currentStep === "role")' in read("static/js/auth-pages.js")
    assert 'showStep("phone");' in read("static/js/auth-pages.js")
    assert 'id="authPhoneStep"' in html
    assert 'id="authProfileStep"' in html
    assert 'name="terms_accepted"' not in html
    assert 'name="role" value="seller" checked' not in html
    assert "با وارد کردن شماره موبایل،" in html
    assert "auth-legal-note" in html


def test_store_directory_exposes_city_filter_and_routing_fallback():
    directory = read("templates/pages/stores/list.html")
    script = read("static/js/pages.js")
    assert 'id="storeCity"' in directory
    assert 'cityInput.value.trim()' in script
    assert 'if(city) qs.set("city",city);' in script
    assert 'function navigationSearchLinks(destination)' in script
    assert 'https://www.google.com/maps/dir/?api=1&destination=' in script
    assert 'destination})' in script
    assert 'stores: initStores' in script


def test_seller_store_forms_capture_geolocation_without_manual_coordinates():
    html = read("templates/pages/seller/dashboard.html")
    script = read("static/js/seller.js")
    assert html.count('data-capture-store-location') >= 2
    assert 'navigator.geolocation.getCurrentPosition' in script
    assert 'position.coords.latitude.toFixed(6)' in script
    assert 'position.coords.longitude.toFixed(6)' in script
    assert 'data-location-status' in html
    assert 'latitude: createForm.latitude?.value || null' in script
    assert 'latitude: editForm.latitude?.value || null' in script
    assert 'method: "PATCH"' in script
    assert 'شهر و نشانی را وارد کن' in script


def test_first_product_form_is_minimal_and_uses_store_defaults():
    html = read("templates/pages/seller/dashboard.html")
    script = read("static/js/seller.js")
    form = html.split('<form id="sellerProductForm"', 1)[1].split("</form>", 1)[0]
    assert 'name="title" required' in form
    assert 'name="price"' in form and 'value=""' in form
    assert 'name="city" type="hidden"' in form
    assert 'name="city" required' not in form
    assert '<details class="seller-optional-product-details">' in form
    assert 'name="image" type="file"' in form
    assert 'productForm.elements.city.value = store.city || ""' in script
    assert 'categorySelect.value = store.category' in script
    assert 'ثبت اولین کالا' in script
    assert 'مشاهده ویترین عمومی' in script


def test_registration_collects_only_core_seller_details_and_optional_coordinates(client):
    html = client.get("/register").get_data(as_text=True)
    script = read("static/js/auth-pages.js")
    assert 'id="registerStoreLocationButton"' in html
    assert 'name="store_latitude"' in html
    assert 'name="store_longitude"' in html
    assert 'navigator.geolocation.getCurrentPosition' in script
    assert 'latitude: (form.elements.store_latitude?.value || "").trim() || null' in script
    assert 'longitude: (form.elements.store_longitude?.value || "").trim() || null' in script
    assert 'name="contact_name"' not in html
    assert 'name="store_address"' not in html
    assert 'name="store_hours"' not in html
    assert 'name="store_description"' not in html
