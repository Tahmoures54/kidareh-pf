import os
import time

from flask import Blueprint, Response, abort, redirect, render_template, request, session, url_for
from xml.sax.saxutils import escape as xml_escape
from urllib.parse import urljoin
import uuid
from ..core import CATEGORIES, current_user, get_connection
from ..data_catalog import CATEGORY_TREE, TRADE_GROUPS

bp = Blueprint("pages", __name__)


@bp.get("/")
def home():
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("index.html", categories=CATEGORIES, category_tree=CATEGORY_TREE, trade_groups=TRADE_GROUPS, csrf_token=session["csrf_token"])


def render_marketplace_page(template: str, **context):
    """Render a standalone marketplace page with the session CSRF token."""
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    context.setdefault("categories", CATEGORIES)
    context.setdefault("category_tree", CATEGORY_TREE)
    context.setdefault("trade_groups", TRADE_GROUPS)
    return render_template(template, csrf_token=session["csrf_token"], **context)


def _registration_required():
    """Send guests to the account form while preserving the requested page."""
    if current_user():
        return None
    destination = request.full_path.rstrip("?")
    return redirect(url_for("pages.register_page", next=destination))


def _admin_required():
    """Keep administration screens private to authenticated administrators."""
    user = current_user()
    if not user:
        return redirect(url_for("pages.register_page", next=request.full_path.rstrip("?")))
    admin_phone = os.environ.get("ADMIN_PHONE", "").strip()
    if not admin_phone or user.get("phone") != admin_phone or not user.get("phone_verified_at"):
        abort(403)
    return None


@bp.get("/search")
def search_page():
    return render_marketplace_page(
        "pages/catalog/search.html",
        query=request.args.get("q", "").strip(),
        selected_category=request.args.get("category", "").strip(),
        city=request.args.get("city", "").strip(),
        categories=CATEGORIES,
    )


@bp.get("/stores")
def stores_page():
    return render_marketplace_page("pages/stores/list.html", query=request.args.get("q", "").strip())


@bp.get("/store/<int:store_id>")
def store_page(store_id: int):
    with get_connection() as connection:
        store = connection.execute(
            "SELECT name, city, description, address FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    meta_title = f"{store['name']} | ویترین کی‌داره" if store else "ویترین فروشگاه | کی‌داره"
    meta_description = (
        f"ویترین {store['name']} در {store['city']}؛ {store['description']}".strip("؛ ")
        if store
        else "کالاهای فروشگاه‌ها را در کی‌داره ببینید."
    )
    structured_data = None
    if store:
        structured_data = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": store["name"],
            "description": store["description"] or meta_description,
            "url": request.url_root.rstrip("/") + request.path,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": store["city"],
                "streetAddress": store["address"] or "",
                "addressCountry": "IR",
            },
        }
    return render_marketplace_page(
        "pages/stores/detail.html",
        store_id=store_id,
        meta_title=meta_title,
        meta_description=meta_description,
        structured_data=structured_data,
    )


@bp.get("/product/<int:product_id>")
def product_page(product_id: int):
    with get_connection() as connection:
        product = connection.execute(
            "SELECT title, description, city, image_path, price FROM listings WHERE id = ?", (product_id,)
        ).fetchone()
    meta_title = f"{product['title']} | کی‌داره" if product else "جزئیات کالا | کی‌داره"
    meta_description = (
        f"{product['title']} در {product['city']}؛ {product['description']}".strip("؛ ")
        if product
        else "کالاهای متنوع را در کی‌داره ببینید."
    )
    meta_image = urljoin(request.url_root, product["image_path"]) if product and product["image_path"] else None
    structured_data = None
    if product:
        structured_data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product["title"],
            "description": product["description"] or meta_description,
            "url": request.url_root.rstrip("/") + request.path,
            "offers": {
                "@type": "Offer",
                "price": int(product["price"] or 0),
                "priceCurrency": "IRR",
                "availability": "https://schema.org/InStock",
                "areaServed": product["city"],
                "itemCondition": "https://schema.org/UsedCondition",
            },
        }
        if meta_image:
            structured_data["image"] = meta_image
    return render_marketplace_page(
        "pages/products/detail.html",
        product_id=product_id,
        meta_title=meta_title,
        meta_description=meta_description,
        meta_type="product",
        meta_image=meta_image,
        structured_data=structured_data,
    )


@bp.get("/robots.txt")
def robots_txt():
    base = request.url_root.rstrip("/")
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /account",
        "Disallow: /seller",
        "Disallow: /admin",
        "Disallow: /messages",
        "Disallow: /support",
        "Disallow: /monetization",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ])
    response = Response(body, mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


# Crawlers ask for the sitemap constantly and the newest pages barely change, so
# the document is rebuilt at most once every ten minutes per process instead of
# on every request (a full sitemap is a 10k-row query and ~1 MB of XML).
SITEMAP_CACHE_SECONDS = 600
_sitemap_cache: dict[str, tuple[float, str]] = {}


@bp.get("/sitemap.xml")
def sitemap_xml():
    base = request.url_root.rstrip("/")
    now = time.monotonic()
    cached = _sitemap_cache.get(base)
    if cached and now - cached[0] < SITEMAP_CACHE_SECONDS:
        xml = cached[1]
    else:
        urls = [("/", None), ("/search", None), ("/stores", None), ("/help", None), ("/guide", None),
                ("/safety", None), ("/terms", None), ("/privacy", None)]
        with get_connection() as connection:
            for row in connection.execute("SELECT id, created_at FROM stores ORDER BY id DESC LIMIT 5000"):
                urls.append((f"/store/{row['id']}", row["created_at"]))
            for row in connection.execute("SELECT id, created_at FROM listings ORDER BY id DESC LIMIT 5000"):
                urls.append((f"/product/{row['id']}", row["created_at"]))
        entries = []
        for path, lastmod in urls:
            lastmod_xml = f"<lastmod>{xml_escape(str(lastmod)[:10])}</lastmod>" if lastmod else ""
            entries.append(f"  <url><loc>{xml_escape(base + path)}</loc>{lastmod_xml}</url>")
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(entries) + "\n</urlset>\n")
        _sitemap_cache[base] = (now, xml)
    response = Response(xml, mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@bp.get("/seller")
def seller_dashboard_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/seller/dashboard.html", categories=CATEGORIES)


@bp.get("/seller/tags")
def seller_tags_page():
    required = _registration_required()
    if required:
        return required
    from .monetization import TAG_PACKAGES

    return render_marketplace_page("pages/seller/tags.html", tag_packages=TAG_PACKAGES)


@bp.get("/monetization")
def monetization_page():
    required = _registration_required()
    if required:
        return required
    # Imported lazily: the monetization module owns the package catalogue.
    from .monetization import PACKAGES, TAG_PACKAGES

    return render_marketplace_page(
        "pages/seller/monetization.html",
        packages=PACKAGES,
        tag_packages=TAG_PACKAGES,
    )


@bp.get("/account")
def account_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/account/profile.html")


@bp.get("/saved")
def saved_products_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/account/saved.html")


@bp.get("/following")
def following_stores_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/account/following.html")


@bp.get("/messages")
def messages_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/account/messages.html")


@bp.get("/support")
def support_page():
    required = _registration_required()
    if required:
        return required
    return render_marketplace_page("pages/account/support.html")


@bp.get("/admin")
def admin_dashboard_page():
    required = _admin_required()
    if required:
        return required
    return render_marketplace_page("pages/admin/dashboard.html")


@bp.get("/admin/reports")
def admin_reports_page():
    required = _admin_required()
    if required:
        return required
    return render_marketplace_page("pages/admin/reports.html")



@bp.get("/help")
def help_page():
    return render_marketplace_page("pages/help.html")


@bp.get("/guide")
def user_guide_page():
    return render_marketplace_page("pages/guide.html")


@bp.get("/safety")
def safety_page():
    return render_marketplace_page("pages/safety.html")


@bp.get("/privacy")
def privacy_page():
    return render_marketplace_page("pages/privacy.html")

@bp.get("/terms")
def terms_page():
    return render_marketplace_page("pages/terms.html")


@bp.get("/login")
def login_page():
    return render_marketplace_page("pages/auth/login.html")


@bp.get("/register")
@bp.get("/signup")
def register_page():
    return render_marketplace_page("pages/auth/register.html")
