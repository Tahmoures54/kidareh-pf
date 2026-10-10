from flask import Blueprint, render_template, request, session
from urllib.parse import urljoin
import uuid
from ..core import CATEGORIES, get_connection

bp = Blueprint("pages", __name__)


@bp.get("/")
def home():
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("index.html", categories=CATEGORIES, csrf_token=session["csrf_token"])


def render_marketplace_page(template: str, **context):
    """Render a standalone marketplace page with the session CSRF token."""
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template(template, csrf_token=session["csrf_token"], **context)


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
        store = connection.execute("SELECT name, city, description FROM stores WHERE id = ?", (store_id,)).fetchone()
    meta_title = f"{store['name']} | ویترین کی‌داره" if store else "ویترین فروشگاه | کی‌داره"
    meta_description = (
        f"ویترین {store['name']} در {store['city']}؛ {store['description']}".strip("؛ ")
        if store
        else "کالاهای فروشگاه‌ها را در کی‌داره ببینید."
    )
    return render_marketplace_page(
        "pages/stores/detail.html",
        store_id=store_id,
        meta_title=meta_title,
        meta_description=meta_description,
    )


@bp.get("/product/<int:product_id>")
def product_page(product_id: int):
    with get_connection() as connection:
        product = connection.execute(
            "SELECT title, description, city, image_path FROM listings WHERE id = ?", (product_id,)
        ).fetchone()
    meta_title = f"{product['title']} | کی‌داره" if product else "جزئیات کالا | کی‌داره"
    meta_description = (
        f"{product['title']} در {product['city']}؛ {product['description']}".strip("؛ ")
        if product
        else "کالاهای متنوع را در کی‌داره ببینید."
    )
    meta_image = urljoin(request.url_root, product["image_path"]) if product and product["image_path"] else None
    return render_marketplace_page(
        "pages/products/detail.html",
        product_id=product_id,
        meta_title=meta_title,
        meta_description=meta_description,
        meta_type="product",
        meta_image=meta_image,
    )


@bp.get("/seller")
def seller_dashboard_page():
    return render_marketplace_page("pages/seller/dashboard.html", categories=CATEGORIES)


@bp.get("/seller/tags")
def seller_tags_page():
    from .monetization import TAG_PACKAGES

    return render_marketplace_page("pages/seller/tags.html", tag_packages=TAG_PACKAGES)


@bp.get("/monetization")
def monetization_page():
    return render_marketplace_page("pages/seller/monetization.html")


@bp.get("/account")
def account_page():
    return render_marketplace_page("pages/account/profile.html")


@bp.get("/saved")
def saved_products_page():
    return render_marketplace_page("pages/account/saved.html")


@bp.get("/following")
def following_stores_page():
    return render_marketplace_page("pages/account/following.html")


@bp.get("/messages")
def messages_page():
    return render_marketplace_page("pages/account/messages.html")


@bp.get("/support")
def support_page():
    return render_marketplace_page("pages/account/support.html")


@bp.get("/admin")
def admin_dashboard_page():
    return render_marketplace_page("pages/admin/dashboard.html")


@bp.get("/admin/reports")
def admin_reports_page():
    return render_marketplace_page("pages/admin/reports.html")


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
