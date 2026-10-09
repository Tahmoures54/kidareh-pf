from flask import Blueprint, render_template, request, session
import uuid
from ..core import CATEGORIES

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
    return render_marketplace_page("pages/stores/detail.html", store_id=store_id)

@bp.get("/product/<int:product_id>")
def product_page(product_id: int):
    return render_marketplace_page("pages/products/detail.html", product_id=product_id)

@bp.get("/seller")
def seller_dashboard_page():
    return render_marketplace_page("pages/seller/dashboard.html")

@bp.get("/account")
def account_page():
    return render_marketplace_page("pages/account/profile.html")

@bp.get("/saved")
def saved_products_page():
    return render_marketplace_page("pages/account/saved.html")

@bp.get("/following")
def following_stores_page():
    return render_marketplace_page("pages/account/following.html")

