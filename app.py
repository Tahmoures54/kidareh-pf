from __future__ import annotations

import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "kidareh.sqlite3")))
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads")))
MAX_IMAGE_BYTES = 4 * 1024 * 1024

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-key")
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 256 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

CATEGORIES = [
    {"id": "home", "name": "خانه و زندگی", "icon": "⌂"},
    {"id": "digital", "name": "دیجیتال", "icon": "▣"},
    {"id": "fashion", "name": "پوشاک", "icon": "✦"},
    {"id": "vehicle", "name": "خودرو", "icon": "↗"},
    {"id": "services", "name": "خدمات", "icon": "⚒"},
    {"id": "other", "name": "سایر", "icon": "＋"},
]

DEMO_LISTINGS = [
    ("گوشی سامسونگ تمیز و سالم", "digital", "تهران", 12800000, "گوشی سالم با حافظه مناسب؛ امکان بررسی حضوری.", "📱", 1),
    ("میز کار چوبی مینیمال", "home", "تبریز", 2450000, "میز مرتب و خوش‌ساخت، مناسب خانه و دفتر کار.", "🪑", 1),
    ("دوچرخه شهری کم‌کارکرد", "vehicle", "تهران", 5600000, "دوچرخه شهری آماده استفاده، بازدید با هماهنگی.", "🚲", 0),
    ("کتانی روزمره در حد نو", "fashion", "شیراز", 980000, "راحت و سبک، وضعیت بسیار خوب.", "👟", 0),
    ("تعمیر و سرویس لپ‌تاپ", "services", "اصفهان", 450000, "عیب‌یابی و سرویس با اعلام هزینه پیش از انجام کار.", "🧰", 1),
    ("چراغ مطالعه مدرن", "home", "رشت", 620000, "نور مناسب مطالعه با طراحی ساده و جمع‌وجور.", "💡", 0),
    ("هدفون بی‌سیم", "digital", "مشهد", 1750000, "هدفون روزمره با کیفیت صدای مناسب.", "🎧", 0),
    ("کوله‌پشتی روزانه", "fashion", "کرج", 890000, "جادار و مناسب دانشگاه و استفاده روزانه.", "🎒", 0),
]


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                city TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL DEFAULT '',
                emoji TEXT NOT NULL DEFAULT '🛍️',
                featured INTEGER NOT NULL DEFAULT 0,
                image_path TEXT NOT NULL DEFAULT '',
                seller_phone TEXT NOT NULL DEFAULT '',
                owner_id INTEGER,
                store_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(listings)")}
        if "image_path" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")
        if "seller_phone" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN seller_phone TEXT NOT NULL DEFAULT ''")
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN owner_id INTEGER")
        if "store_id" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN store_id INTEGER")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'buyer',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "role" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'buyer'")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS store_follows (
                user_id INTEGER NOT NULL,
                store_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, store_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS saved_products (
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, listing_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE
            )
        """)
        store_count = connection.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
        if store_count == 0:
            connection.executemany(
                "INSERT INTO stores (owner_id, name, city, description) VALUES (NULL, ?, ?, ?)",
                [
                    ("خانه‌چین", "تهران", "لوازم کاربردی خانه و زندگی؛ بازدید و خرید حضوری"),
                    ("دیجیتال‌کده", "تبریز", "کالاهای دیجیتال و لوازم جانبی"),
                    ("بازار محلی", "شیراز", "کالاهای روزمره و انتخاب‌های محلی"),
                ],
            )
        count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        if count == 0:
            connection.executemany(
                """
                INSERT INTO listings
                    (title, category, city, price, description, emoji, featured)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                DEMO_LISTINGS,
            )
        connection.execute("""
            UPDATE listings SET store_id = (
                SELECT id FROM stores
                WHERE stores.owner_id IS NULL
                  AND ((listings.category = 'home' AND stores.name = 'خانه‌چین')
                    OR (listings.category = 'digital' AND stores.name = 'دیجیتال‌کده')
                    OR (listings.category NOT IN ('home', 'digital') AND stores.name = 'بازار محلی'))
                LIMIT 1
            )
            WHERE store_id IS NULL
        """)


def serialize_listing(row: sqlite3.Row, include_contact: bool = False) -> dict[str, Any]:
    item = dict(row)
    item["featured"] = bool(item["featured"])
    item.pop("password_hash", None)
    if not include_contact:
        item.pop("seller_phone", None)
    item["can_edit"] = bool(session.get("user_id") and item.get("owner_id") == session.get("user_id"))
    return item


@app.get("/")
def home():
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("index.html", categories=CATEGORIES, csrf_token=session["csrf_token"])

def render_marketplace_page(template: str, **context):
    """Render a standalone marketplace page with the session CSRF token."""
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template(template, csrf_token=session["csrf_token"], **context)


@app.get("/search")
def search_page():
    return render_marketplace_page(
        "search.html",
        query=request.args.get("q", "").strip(),
        selected_category=request.args.get("category", "").strip(),
        city=request.args.get("city", "").strip(),
        categories=CATEGORIES,
    )


@app.get("/stores")
def stores_page():
    return render_marketplace_page("stores.html", query=request.args.get("q", "").strip())


@app.get("/store/<int:store_id>")
def store_page(store_id: int):
    return render_marketplace_page("store_detail.html", store_id=store_id)


@app.get("/product/<int:product_id>")
def product_page(product_id: int):
    return render_marketplace_page("product_detail.html", product_id=product_id)


@app.get("/seller")
def seller_dashboard_page():
    return render_marketplace_page("seller_dashboard.html")


@app.get("/account")
def account_page():
    return render_marketplace_page("account.html")


@app.get("/saved")
def saved_products_page():
    return render_marketplace_page("saved.html")


@app.get("/following")
def following_stores_page():
    return render_marketplace_page("following.html")




def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_connection() as connection:
        row = connection.execute("SELECT id, name, phone, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        session.clear()
        return None
    return dict(row)


def csrf_valid():
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and __import__("hmac").compare_digest(expected, supplied))


@app.post("/api/auth/signup")
def auth_signup():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    payload = request.get_json(silent=True) or {}
    name, phone, password = payload.get("name", ""), payload.get("phone", ""), payload.get("password", "")
    role = payload.get("role", "buyer")
    if role not in {"buyer", "seller"}:
        return jsonify({"error": "invalid_role", "message": "نوع حساب معتبر نیست."}), 400
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "invalid_name", "message": "نام را وارد کنید."}), 400
    if not isinstance(phone, str):
        return jsonify({"error": "invalid_phone", "message": "شماره همراه معتبر وارد کنید."}), 400
    phone = phone.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    phone = re.sub(r"[\s()\-]", "", phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return jsonify({"error": "invalid_phone", "message": "شماره همراه باید مانند 09123456789 باشد."}), 400
    if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
        return jsonify({"error": "weak_password", "message": "رمز عبور باید حداقل ۱۰ نویسه باشد."}), 400
    try:
        with get_connection() as connection:
            cursor = connection.execute("INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)", (name.strip(), phone, generate_password_hash(password), role))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "phone_exists", "message": "این شماره قبلاً ثبت شده است؛ وارد شوید."}), 409
    session.clear()
    session["user_id"] = user_id
    session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": {"id": user_id, "name": name.strip(), "phone": phone, "role": role}, "csrf_token": session["csrf_token"]}), 201


@app.post("/api/auth/login")
def auth_login():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    payload = request.get_json(silent=True) or {}
    phone, password = payload.get("phone", ""), payload.get("password", "")
    if not isinstance(phone, str) or not isinstance(password, str):
        return jsonify({"error": "invalid_credentials", "message": "شماره یا رمز عبور نادرست است."}), 400
    phone = phone.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    phone = re.sub(r"[\s()\-]", "", phone)
    with get_connection() as connection:
        user = connection.execute("SELECT id, name, phone, password_hash, role FROM users WHERE phone = ?", (phone,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid_credentials", "message": "شماره یا رمز عبور نادرست است."}), 401
    session.clear()
    session["user_id"] = user["id"]
    session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": {"id": user["id"], "name": user["name"], "phone": user["phone"], "role": user["role"]}, "csrf_token": session["csrf_token"]})


@app.post("/api/auth/become-seller")
def become_seller():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    with get_connection() as connection:
        connection.execute("UPDATE users SET role = 'seller' WHERE id = ?", (user["id"],))
    user["role"] = "seller"
    return jsonify({"user": user})


@app.get("/api/auth/me")
def auth_me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": user, "csrf_token": session["csrf_token"]})


@app.post("/api/auth/logout")
def auth_logout():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "kidareh-pf"})




@app.get("/api/stores")
def list_stores():
    query = request.args.get("q", "").strip()[:100]
    city = request.args.get("city", "").strip()[:60]
    sql = """
        SELECT s.*, COUNT(DISTINCT l.id) AS product_count,
               COUNT(DISTINCT f.user_id) AS follower_count
        FROM stores s
        LEFT JOIN listings l ON l.store_id = s.id
        LEFT JOIN store_follows f ON f.store_id = s.id
        WHERE 1=1
    """
    params: list[Any] = []
    if query:
        sql += " AND (s.name LIKE ? OR s.description LIKE ? OR s.city LIKE ?)"
        term = f"%{query}%"
        params.extend([term, term, term])
    if city:
        sql += " AND s.city = ?"
        params.append(city)
    sql += " GROUP BY s.id ORDER BY s.id DESC LIMIT 100"
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return jsonify({"items": [dict(row) for row in rows], "count": len(rows)})


@app.get("/api/my/store")
def my_store():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM stores WHERE owner_id = ?", (user["id"],)).fetchone()
    return jsonify({"item": dict(row) if row else None})


@app.post("/api/stores")
def create_store():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای ساخت ویترین وارد حساب شوید."}), 401
    if user.get("role") != "seller":
        return jsonify({"error": "seller_account_required", "message": "برای ساخت ویترین با نوع حساب فروشنده وارد شوید."}), 403
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    name, city, description = payload.get("name", ""), payload.get("city", ""), payload.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "invalid_store_name", "message": "نام فروشگاه را وارد کنید."}), 400
    if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
        return jsonify({"error": "invalid_store_city", "message": "شهر را وارد کنید."}), 400
    if not isinstance(description, str) or len(description.strip()) > 500:
        return jsonify({"error": "invalid_store_description"}), 400
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO stores (owner_id, name, city, description) VALUES (?, ?, ?, ?)",
                (user["id"], name.strip(), city.strip(), description.strip()),
            )
            row = connection.execute("SELECT * FROM stores WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "store_exists", "message": "برای این حساب قبلاً ویترین ساخته شده است."}), 409
    return jsonify({"item": dict(row)}), 201


@app.get("/api/stores/<int:store_id>")
def store_detail(store_id: int):
    with get_connection() as connection:
        store = connection.execute("""
            SELECT s.*, COUNT(DISTINCT l.id) AS product_count,
                   COUNT(DISTINCT f.user_id) AS follower_count
            FROM stores s
            LEFT JOIN listings l ON l.store_id = s.id
            LEFT JOIN store_follows f ON f.store_id = s.id
            WHERE s.id = ? GROUP BY s.id
        """, (store_id,)).fetchone()
        if store is None:
            return jsonify({"error": "store_not_found"}), 404
        products = connection.execute(
            "SELECT * FROM listings WHERE store_id = ? ORDER BY id DESC LIMIT 100", (store_id,)
        ).fetchall()
        user = current_user()
        following = False
        if user:
            following = connection.execute(
                "SELECT 1 FROM store_follows WHERE user_id = ? AND store_id = ?",
                (user["id"], store_id),
            ).fetchone() is not None
    return jsonify({"store": dict(store), "items": [serialize_listing(row) for row in products], "following": following})


@app.post("/api/stores/<int:store_id>/follow")
def toggle_store_follow(store_id: int):
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای دنبال‌کردن فروشگاه وارد شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM stores WHERE id = ?", (store_id,)).fetchone() is None:
            return jsonify({"error": "store_not_found"}), 404
        existing = connection.execute(
            "SELECT 1 FROM store_follows WHERE user_id = ? AND store_id = ?", (user["id"], store_id)
        ).fetchone()
        if existing:
            connection.execute("DELETE FROM store_follows WHERE user_id = ? AND store_id = ?", (user["id"], store_id))
            following = False
        else:
            connection.execute("INSERT INTO store_follows (user_id, store_id) VALUES (?, ?)", (user["id"], store_id))
            following = True
        count = connection.execute("SELECT COUNT(*) FROM store_follows WHERE store_id = ?", (store_id,)).fetchone()[0]
    return jsonify({"following": following, "follower_count": count})


@app.get("/api/stores/following")
def followed_stores():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT s.*, COUNT(DISTINCT l.id) AS product_count,
                   COUNT(DISTINCT f2.user_id) AS follower_count
            FROM store_follows f
            JOIN stores s ON s.id = f.store_id
            LEFT JOIN listings l ON l.store_id = s.id
            LEFT JOIN store_follows f2 ON f2.store_id = s.id
            WHERE f.user_id = ? GROUP BY s.id ORDER BY f.created_at DESC
        """, (user["id"],)).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@app.post("/api/listings/<int:listing_id>/save")
def toggle_saved_listing(listing_id: int):
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای ذخیره دائمی کالا وارد حساب شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,)).fetchone() is None:
            return jsonify({"error": "product_not_found"}), 404
        existing = connection.execute(
            "SELECT 1 FROM saved_products WHERE user_id = ? AND listing_id = ?", (user["id"], listing_id)
        ).fetchone()
        if existing:
            connection.execute("DELETE FROM saved_products WHERE user_id = ? AND listing_id = ?", (user["id"], listing_id))
            saved = False
        else:
            connection.execute("INSERT INTO saved_products (user_id, listing_id) VALUES (?, ?)", (user["id"], listing_id))
            saved = True
    return jsonify({"saved": saved})


@app.get("/api/products/saved")
def saved_listings():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT l.* FROM saved_products s JOIN listings l ON l.id = s.listing_id
            WHERE s.user_id = ? ORDER BY s.created_at DESC
        """, (user["id"],)).fetchall()
    return jsonify({"items": [serialize_listing(row) for row in rows]})

@app.get("/api/categories")
def categories():
    return jsonify({"items": CATEGORIES})


@app.get("/api/listings")
def listings():
    query = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:40]
    city = request.args.get("city", "").strip()[:60]

    sql = "SELECT * FROM listings WHERE 1=1"
    parameters: list[Any] = []
    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR city LIKE ?)"
        term = f"%{query}%"
        parameters.extend([term, term, term])
    if category and category != "all":
        sql += " AND category = ?"
        parameters.append(category)
    if city and city != "همه شهرها":
        sql += " AND city = ?"
        parameters.append(city)
    sql += " ORDER BY featured DESC, id DESC LIMIT 100"

    with get_connection() as connection:
        rows = connection.execute(sql, parameters).fetchall()
    items = [serialize_listing(row) for row in rows]
    return jsonify({"items": items, "count": len(items)})


def inspect_image(upload) -> tuple[bytes, str] | None:
    """Identify raster image data from its signature, not the supplied filename."""
    if upload is None or not upload.filename:
        return None
    content = upload.stream.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return content, ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return content, ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return content, ".webp"
    raise ValueError("invalid_image")


@app.post("/api/listings")
def create_listing():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای ثبت آگهی ابتدا وارد حساب شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    is_multipart = bool(request.content_type and request.content_type.startswith("multipart/form-data"))
    payload = request.form if is_multipart else request.get_json(silent=True)
    if payload is None or not hasattr(payload, "get"):
        return jsonify({"error": "invalid_payload"}), 400

    title = payload.get("title")
    category = payload.get("category")
    city = payload.get("city")
    description = payload.get("description", "")
    seller_phone = payload.get("seller_phone", "")
    raw_price = payload.get("price", 0)
    try:
        price = int(raw_price) if not isinstance(raw_price, bool) else -1
    except (TypeError, ValueError):
        price = -1

    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100:
        return jsonify({"error": "invalid_title", "message": "عنوان باید بین ۱ تا ۱۰۰ نویسه باشد."}), 400
    if not isinstance(category, str) or category not in {item["id"] for item in CATEGORIES}:
        return jsonify({"error": "invalid_category"}), 400
    if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
        return jsonify({"error": "invalid_city"}), 400
    if not isinstance(description, str) or len(description.strip()) > 1000:
        return jsonify({"error": "invalid_description"}), 400
    if not isinstance(seller_phone, str):
        return jsonify({"error": "invalid_seller_phone", "message": "شماره تماس معتبر وارد کنید."}), 400
    digit_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    seller_phone = seller_phone.translate(digit_map)
    seller_phone = re.sub(r"[\s()\-]", "", seller_phone)
    if seller_phone and not re.fullmatch(r"09\d{9}", seller_phone):
        return jsonify({"error": "invalid_seller_phone", "message": "شماره همراه باید مانند 09123456789 باشد."}), 400
    if price < 0 or price > 10**12:
        return jsonify({"error": "invalid_price"}), 400

    image_content = None
    upload = request.files.get("image") if is_multipart else None
    if upload and upload.filename:
        try:
            image_content = inspect_image(upload)
        except ValueError as error:
            reason = str(error)
            status = 413 if reason == "image_too_large" else 400
            return jsonify({"error": reason, "message": "تصویر باید JPG، PNG یا WebP و حداکثر ۴ مگابایت باشد."}), status

    image_path = ""
    if image_content:
        binary, extension = image_content
        filename = f"{uuid.uuid4().hex}{extension}"
        target_folder = Path(app.config["UPLOAD_FOLDER"])
        target_folder.mkdir(parents=True, exist_ok=True)
        (target_folder / filename).write_bytes(binary)
        image_path = f"/static/uploads/{filename}"

    with get_connection() as connection:
        store = connection.execute("SELECT id FROM stores WHERE owner_id = ?", (user["id"],)).fetchone()
        if store is None:
            return jsonify({"error": "store_required", "message": "برای افزودن کالا، ابتدا ویترین فروشگاه خود را بسازید."}), 409
        cursor = connection.execute(
            """
            INSERT INTO listings (title, category, city, price, description, emoji, featured, image_path, seller_phone, owner_id, store_id)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (title.strip(), category, city.strip(), price, description.strip(), "🛍️", image_path, seller_phone, user["id"], store["id"]),
        )
        listing_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()

    return jsonify({"item": serialize_listing(row, include_contact=True)}), 201



@app.route("/api/listings/<int:listing_id>", methods=["PATCH", "DELETE"])
def manage_listing(listing_id: int):
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای مدیریت آگهی وارد شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if row is None:
            return jsonify({"error": "listing_not_found"}), 404
        if row["owner_id"] != user["id"]:
            return jsonify({"error": "listing_forbidden", "message": "فقط صاحب آگهی می‌تواند آن را تغییر دهد."}), 403
        if request.method == "DELETE":
            connection.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
            return jsonify({"ok": True})
        payload = request.get_json(silent=True) or {}
        allowed = {"title", "category", "city", "price", "description", "seller_phone"}
        if not payload or set(payload) - allowed:
            return jsonify({"error": "invalid_payload"}), 400
        title = payload.get("title", row["title"])
        category = payload.get("category", row["category"])
        city = payload.get("city", row["city"])
        description = payload.get("description", row["description"])
        price = payload.get("price", row["price"])
        phone = payload.get("seller_phone", row["seller_phone"])
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100:
            return jsonify({"error": "invalid_title"}), 400
        if not isinstance(category, str) or category not in {item["id"] for item in CATEGORIES}:
            return jsonify({"error": "invalid_category"}), 400
        if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
            return jsonify({"error": "invalid_city"}), 400
        if not isinstance(description, str) or len(description) > 1000:
            return jsonify({"error": "invalid_description"}), 400
        try:
            price = int(price)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_price"}), 400
        if price < 0 or price > 10**12:
            return jsonify({"error": "invalid_price"}), 400
        if not isinstance(phone, str):
            return jsonify({"error": "invalid_seller_phone"}), 400
        phone = phone.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        phone = re.sub(r"[\s()\-]", "", phone)
        if phone and not re.fullmatch(r"09\d{9}", phone):
            return jsonify({"error": "invalid_seller_phone"}), 400
        connection.execute("UPDATE listings SET title=?, category=?, city=?, price=?, description=?, seller_phone=? WHERE id=?", (title.strip(), category, city.strip(), price, description.strip(), phone, listing_id))
        updated = connection.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        return jsonify({"item": serialize_listing(updated, include_contact=True)})


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "request_too_large", "message": "حجم درخواست بیش از حد مجاز است."}), 413

@app.get("/api/listings/<int:listing_id>")
def listing_detail(listing_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "listing_not_found"}), 404
    return jsonify({"item": serialize_listing(row, include_contact=True)})


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    return render_template("index.html", categories=CATEGORIES), 404


initialize_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
