import re
import sqlite3
from typing import Any
from flask import Blueprint, jsonify, request
from ..core import current_user, csrf_valid, get_connection, serialize_listing

bp = Blueprint("stores", __name__)


@bp.get("/api/stores")
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

@bp.get("/api/my/store")
def my_store():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM stores WHERE owner_id = ?", (user["id"],)).fetchone()
    return jsonify({"item": dict(row) if row else None})

@bp.post("/api/stores")
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
    category = payload.get("category", "")
    contact_name = payload.get("contact_name", user.get("name", ""))
    address = payload.get("address", "")
    hours = payload.get("hours", "")
    in_person = 1 if payload.get("in_person", True) else 0
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "invalid_store_name", "message": "نام فروشگاه را وارد کنید."}), 400
    if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
        return jsonify({"error": "invalid_store_city", "message": "شهر را وارد کنید."}), 400
    if not isinstance(description, str) or len(description.strip()) > 500:
        return jsonify({"error": "invalid_store_description"}), 400
    for value, maximum in ((category, 80), (contact_name, 80), (address, 300), (hours, 120)):
        if not isinstance(value, str) or len(value.strip()) > maximum:
            return jsonify({"error": "invalid_store_details", "message": "اطلاعات فروشگاه معتبر نیست."}), 400
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """INSERT INTO stores (owner_id, name, city, description, category, contact_name, address, hours, in_person)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user["id"], name.strip(), city.strip(), description.strip(), category.strip(), contact_name.strip(),
                 address.strip(), hours.strip(), in_person),
            )
            row = connection.execute("SELECT * FROM stores WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "store_exists", "message": "برای این حساب قبلاً ویترین ساخته شده است."}), 409
    return jsonify({"item": dict(row)}), 201

@bp.patch("/api/stores/<int:store_id>")
def update_store(store_id: int):
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای ویرایش فروشگاه وارد شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    allowed = {"name", "city", "description"}
    if not payload or set(payload) - allowed:
        return jsonify({"error": "invalid_payload"}), 400
    with get_connection() as connection:
        store = connection.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
        if store is None:
            return jsonify({"error": "store_not_found"}), 404
        if store["owner_id"] != user["id"]:
            return jsonify({"error": "store_forbidden", "message": "فقط صاحب فروشگاه می‌تواند اطلاعات آن را تغییر دهد."}), 403
        name = payload.get("name", store["name"])
        city = payload.get("city", store["city"])
        description = payload.get("description", store["description"])
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            return jsonify({"error": "invalid_store_name", "message": "نام فروشگاه باید حداکثر ۸۰ نویسه باشد."}), 400
        if not isinstance(city, str) or not city.strip() or len(city.strip()) > 60:
            return jsonify({"error": "invalid_store_city", "message": "شهر را درست وارد کنید."}), 400
        if not isinstance(description, str) or len(description.strip()) > 500:
            return jsonify({"error": "invalid_store_description", "message": "توضیحات حداکثر ۵۰۰ نویسه باشد."}), 400
        connection.execute("UPDATE stores SET name = ?, city = ?, description = ? WHERE id = ?", (name.strip(), city.strip(), description.strip(), store_id))
        updated = connection.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    return jsonify({"item": dict(updated)})

@bp.get("/api/stores/<int:store_id>")
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

@bp.post("/api/stores/<int:store_id>/follow")
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

@bp.get("/api/stores/following")
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

@bp.post("/api/listings/<int:listing_id>/save")
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

@bp.get("/api/products/saved")
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

