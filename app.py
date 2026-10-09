from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "kidareh.sqlite3")))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-key")
app.config["JSON_AS_ASCII"] = False

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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
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


def serialize_listing(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["featured"] = bool(item["featured"])
    return item


@app.get("/")
def home():
    return render_template("index.html", categories=CATEGORIES)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "kidareh-pf"})


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


@app.post("/api/listings")
def create_listing():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json"}), 400

    title = payload.get("title")
    category = payload.get("category")
    city = payload.get("city")
    description = payload.get("description", "")
    price = payload.get("price", 0)

    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100:
        return jsonify({"error": "invalid_title", "message": "عنوان باید بین ۱ تا ۱۰۰ نویسه باشد."}), 400
    if not isinstance(category, str) or category not in {item["id"] for item in CATEGORIES}:
        return jsonify({"error": "invalid_category"}), 400
    if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
        return jsonify({"error": "invalid_city"}), 400
    if not isinstance(description, str) or len(description.strip()) > 1000:
        return jsonify({"error": "invalid_description"}), 400
    if isinstance(price, bool) or not isinstance(price, int) or price < 0 or price > 10**12:
        return jsonify({"error": "invalid_price"}), 400

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO listings (title, category, city, price, description, emoji, featured)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (title.strip(), category, city.strip(), price, description.strip(), "🛍️"),
        )
        listing_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()

    return jsonify({"item": serialize_listing(row)}), 201


@app.get("/api/listings/<int:listing_id>")
def listing_detail(listing_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "listing_not_found"}), 404
    return jsonify({"item": serialize_listing(row)})


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    return render_template("index.html", categories=CATEGORIES), 404


initialize_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
