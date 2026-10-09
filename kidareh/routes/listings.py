import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from flask import Blueprint, current_app, jsonify, request
from ..core import CATEGORIES, MAX_IMAGE_BYTES, current_user, csrf_valid, get_connection, serialize_listing

bp = Blueprint("listings", __name__)


def _delete_listing_image(image_path: str) -> None:
    """Remove an uploaded listing image from disk if it lives under UPLOAD_FOLDER."""
    if not image_path or not isinstance(image_path, str):
        return
    if not image_path.startswith("/static/uploads/"):
        return
    filename = image_path.rsplit("/", 1)[-1]
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return
    target = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    try:
        if target.is_file():
            target.unlink()
    except OSError:
        pass


def _attach_active_tags(items):
    if not items:
        return items
    now = datetime.now(timezone.utc).isoformat()
    ids = [int(item["id"]) for item in items]
    placeholders = ",".join("?" for _ in ids)
    with get_connection() as connection:
        rows = connection.execute(
            f"""SELECT listing_id, tag_type, ends_at FROM listing_tags
                WHERE status='active' AND ends_at>? AND listing_id IN ({placeholders})
                ORDER BY ends_at DESC""",
            [now, *ids],
        ).fetchall()
    active = {}
    for row in rows:
        active.setdefault(row["listing_id"], {"type": row["tag_type"], "ends_at": row["ends_at"]})
    labels = {"listing_tag_sale": "حراج", "listing_tag_special": "فروش ویژه", "listing_tag_discount": "تخفیف‌دار"}
    for item in items:
        tag = active.get(int(item["id"]))
        item["paid_tag"] = ({**tag, "label": labels.get(tag["type"], "ویژه")} if tag else None)
    return items


@bp.get("/api/categories")
def categories():
    return jsonify({"items": CATEGORIES})

@bp.get("/api/listings")
def listings():
    query = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:40]
    city = request.args.get("city", "").strip()[:60]
    near_lat, near_lon = request.args.get("lat", type=float), request.args.get("lon", type=float)
    radius_km = min(100.0, max(1.0, request.args.get("radius_km", default=25.0, type=float) or 25.0))
    use_nearby = near_lat is not None and near_lon is not None and -90 <= near_lat <= 90 and -180 <= near_lon <= 180

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
    if use_nearby:
        # Only candidates with coordinates; rough bounding box cuts the scan before haversine.
        sql += " AND latitude IS NOT NULL AND longitude IS NOT NULL"
        delta_lat = radius_km / 111.0
        cos_lat = max(0.01, abs(math.cos(math.radians(near_lat))))
        delta_lon = radius_km / (111.0 * cos_lat)
        sql += " AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
        parameters.extend([
            near_lat - delta_lat, near_lat + delta_lat,
            near_lon - delta_lon, near_lon + delta_lon,
        ])
    sql += " ORDER BY featured DESC, id DESC LIMIT 300"

    with get_connection() as connection:
        listing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(listings)")}
        if "featured_until" not in listing_columns:
            connection.execute("ALTER TABLE listings ADD COLUMN featured_until TEXT NOT NULL DEFAULT ''")
        now = datetime.now(timezone.utc).isoformat()
        connection.execute("UPDATE listings SET featured=0 WHERE featured=1 AND featured_until<>'' AND featured_until<?", (now,))
        rows = connection.execute(sql, parameters).fetchall()
    items = _attach_active_tags([serialize_listing(row) for row in rows])
    if use_nearby:
        for item in items:
            lat, lon = item.get("latitude"), item.get("longitude")
            item["distance_km"] = None
            if lat is not None and lon is not None:
                dlat = math.radians(float(lat) - near_lat)
                dlon = math.radians(float(lon) - near_lon)
                a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(near_lat)) * math.cos(math.radians(float(lat))) * math.sin(dlon / 2) ** 2
                item["distance_km"] = round(6371 * 2 * math.asin(min(1, math.sqrt(a))), 2)
        items = [item for item in items if item["distance_km"] is not None and item["distance_km"] <= radius_km]
        items.sort(key=lambda item: item["distance_km"])
    return jsonify({"items": items[:100], "count": len(items), "nearby": use_nearby, "radius_km": radius_km if use_nearby else None})

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

@bp.post("/api/listings")
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
    try:
        latitude = float(payload.get("latitude")) if payload.get("latitude") not in (None, "") else None
        longitude = float(payload.get("longitude")) if payload.get("longitude") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error":"invalid_coordinates"}), 400
    if (latitude is None) != (longitude is None) or (latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180)):
        return jsonify({"error":"invalid_coordinates"}), 400
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
        target_folder = Path(current_app.config["UPLOAD_FOLDER"])
        target_folder.mkdir(parents=True, exist_ok=True)
        (target_folder / filename).write_bytes(binary)
        image_path = f"/static/uploads/{filename}"

    with get_connection() as connection:
        store = connection.execute("SELECT id FROM stores WHERE owner_id = ?", (user["id"],)).fetchone()
        if store is None:
            return jsonify({"error": "store_required", "message": "برای افزودن کالا، ابتدا ویترین فروشگاه خود را بسازید."}), 409
        cursor = connection.execute(
            """
            INSERT INTO listings (title, category, city, price, description, emoji, featured, image_path, seller_phone, owner_id, store_id, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (title.strip(), category, city.strip(), price, description.strip(), "🛍️", image_path, seller_phone, user["id"], store["id"], latitude, longitude),
        )
        listing_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()

    return jsonify({"item": _attach_active_tags([serialize_listing(row, include_contact=True)])[0]}), 201

@bp.route("/api/listings/<int:listing_id>", methods=["PATCH", "DELETE"])
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
            image_path = row["image_path"] if row["image_path"] else ""
            connection.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        else:
            image_path = None
            payload = request.get_json(silent=True) or {}
            allowed = {"title", "category", "city", "price", "description", "seller_phone", "latitude", "longitude"}
            if not payload or set(payload) - allowed:
                return jsonify({"error": "invalid_payload"}), 400
            title = payload.get("title", row["title"])
            category = payload.get("category", row["category"])
            city = payload.get("city", row["city"])
            description = payload.get("description", row["description"])
            price = payload.get("price", row["price"])
            phone = payload.get("seller_phone", row["seller_phone"])
            try:
                latitude = float(payload.get("latitude", row["latitude"])) if payload.get("latitude", row["latitude"]) not in (None, "") else None
                longitude = float(payload.get("longitude", row["longitude"])) if payload.get("longitude", row["longitude"]) not in (None, "") else None
            except (TypeError, ValueError):
                return jsonify({"error": "invalid_coordinates"}), 400
            if (latitude is None) != (longitude is None) or (latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180)):
                return jsonify({"error": "invalid_coordinates"}), 400
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
            connection.execute(
                "UPDATE listings SET title=?, category=?, city=?, price=?, description=?, seller_phone=?, latitude=?, longitude=? WHERE id=?",
                (title.strip(), category, city.strip(), price, description.strip(), phone, latitude, longitude, listing_id),
            )
            updated = connection.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
            return jsonify({"item": _attach_active_tags([serialize_listing(updated, include_contact=True)])[0]})
    if request.method == "DELETE":
        _delete_listing_image(image_path)
        return jsonify({"ok": True})
    return jsonify({"error": "method_not_allowed"}), 405

@bp.get("/api/listings/<int:listing_id>")
def listing_detail(listing_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "listing_not_found"}), 404
    return jsonify({"item": _attach_active_tags([serialize_listing(row, include_contact=True)])[0]})

