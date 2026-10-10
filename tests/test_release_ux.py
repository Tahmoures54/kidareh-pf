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
def test_mobile_bottom_nav_has_four_primary_tabs(client):
    for path in ("/", "/stores"):
        html = client.get(path).get_data(as_text=True)
        nav = re.search(r'<nav class="mobile-bottom-nav".*?</nav>', html, re.S).group(0)
        labels = re.findall(r"<small>(.*?)</small>", nav)
        assert labels == ["خانه", "جست‌وجو", "ثبت", "پروفایل"], path


def test_home_has_single_primary_cta_above_the_fold():
    html = read("templates/index.html")
    hero = html[html.index('class="home-intro"'):html.index('class="home-intro-art"')]
    assert hero.count("button-primary") == 1


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
    assert 'CACHE_VERSION = "v4"' in sw
    for asset in ("/static/offline.html", "/static/css/style.css", "/static/css/theme-mh.css",
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
