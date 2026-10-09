import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from flask import Blueprint, current_app, jsonify, request
from ..core import CATEGORIES, MAX_IMAGE_BYTES, current_user, csrf_valid, get_connection, serialize_listing

bp = Blueprint("listings", __name__, url_prefix="/api")


def categories():
    return jsonify({"items": CATEGORIES})

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

def listing_detail(listing_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "listing_not_found"}), 404
    return jsonify({"item": serialize_listing(row, include_contact=True)})

