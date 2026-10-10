import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from flask import Blueprint, current_app, jsonify, request
from ..core import CATEGORIES, MAX_IMAGE_BYTES, current_user, csrf_valid, get_connection, serialize_listing
from ..data_catalog import CATEGORY_ALLOWED_IDS, CATEGORY_GROUPS, CATEGORY_TREE, IRAN_LOCATIONS, TRADE_GROUPS, get_villages

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


def _fts_match_query(raw: str) -> str | None:
    """Build a safe FTS5 MATCH string from user input (AND of quoted tokens)."""
    tokens = re.findall(r"[\w\u0600-\u06FF]+", raw, flags=re.UNICODE)
    if not tokens:
        return None
    # Quote each token so FTS special characters cannot break the query.
    return " AND ".join(f'"{token}"' for token in tokens[:12])


@bp.get("/api/categories")
def categories():
    return jsonify({
        "items": CATEGORIES,
        "subcategories": [
            {"id": item["value"], "name": item["text"], "group_id": group["id"], "group": group["group"]}
            for group in CATEGORY_TREE for item in group["types"]
        ],
    })


@bp.get("/api/locations")
def locations():
    """Search all bundled cities and villages without sending the directory to every visitor."""
    query = request.args.get("q", "").strip().replace("ي", "ی").replace("ك", "ک")[:80]
    kind = request.args.get("kind", "all").strip().lower()
    provinces = {item["id"]: item["name"] for item in IRAN_LOCATIONS["provinces"]}
    counties = {item["id"]: item["name"] for item in IRAN_LOCATIONS["counties"]}
    candidates = []
    if len(query) < 2:
        # Populate the closed-by-default combobox with familiar choices from the
        # canonical Iranian city directory. Full city/village search stays server-side.
        if query or kind not in {"all", "city"}:
            return jsonify({"items": []})
        popular_names = [
            "تهران", "مشهد", "اصفهان", "کرج", "شیراز", "تبریز", "قم",
            "اهواز", "کرمانشاه", "رشت", "کرمان", "یزد", "ساری", "بندرعباس", "اراک",
        ]
        city_by_name = {
            item["name"].replace("ي", "ی").replace("ك", "ک"): item
            for item in IRAN_LOCATIONS["cities"]
        }
        for popular_name in popular_names:
            item = city_by_name.get(popular_name)
            if item:
                candidates.append({
                    "id": item["id"], "name": item["name"], "type": "city",
                    "province": provinces.get(item["province_id"], ""),
                    "county": counties.get(item["county_id"], ""),
                })
        return jsonify({"items": candidates, "count": len(candidates),
                        "source_year": IRAN_LOCATIONS["source_year"]})
    if kind in {"all", "city"}:
        for item in IRAN_LOCATIONS["cities"]:
            name = item["name"].replace("ي", "ی").replace("ك", "ک")
            if query in name:
                candidates.append({
                    "id": item["id"], "name": item["name"], "type": "city",
                    "province": provinces.get(item["province_id"], ""),
                    "county": counties.get(item["county_id"], ""),
                })
    if kind in {"all", "village"}:
        for item in get_villages():
            name = item.get("name", "").replace("ي", "ی").replace("ك", "ک")
            if query in name:
                candidates.append({
                    "id": item.get("id"), "name": item.get("name", ""), "type": "village",
                    "province": provinces.get(item.get("province_id"), ""),
                    "county": counties.get(item.get("county_id"), ""),
                })
    candidates.sort(key=lambda item: (not item["name"].replace("ي", "ی").replace("ك", "ک").startswith(query), item["type"] != "city", item["name"]))
    seen, items = set(), []
    for item in candidates:
        key = (item["name"], item["type"], item["province"], item["county"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= 25:
            break
    return jsonify({"items": items, "count": len(items), "source_year": IRAN_LOCATIONS["source_year"],
                    "villages_available": bool(get_villages())})


@bp.get("/api/trades")
def trades():
    return jsonify({"items": TRADE_GROUPS})

@bp.get("/api/listings")
def listings():
    query = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:40]
    city = request.args.get("city", "").strip()[:100]
    near_lat, near_lon = request.args.get("lat", type=float), request.args.get("lon", type=float)
    radius_km = min(100.0, max(1.0, request.args.get("radius_km", default=25.0, type=float) or 25.0))
    use_nearby = near_lat is not None and near_lon is not None and -90 <= near_lat <= 90 and -180 <= near_lon <= 180
    page_size = min(100, max(1, request.args.get("limit", default=50, type=int) or 50))
    # Keyset cursor: continue after this id (older / lower id when sorting featured DESC, id DESC).
    before_id = request.args.get("before_id", type=int)

    parameters: list[Any] = []
    fts_match = _fts_match_query(query) if query else None

    if fts_match:
        sql = """
            SELECT listings.*
            FROM listings
            INNER JOIN listings_fts ON listings_fts.rowid = listings.id
            WHERE listings_fts MATCH ?
        """
        parameters.append(fts_match)
    else:
        sql = "SELECT * FROM listings WHERE 1=1"

    if category and category != "all":
        category_ids = [category]
        category_ids.extend(CATEGORY_GROUPS.get(category, []))
        category_ids = list(dict.fromkeys(category_ids))
        placeholders = ",".join("?" for _ in category_ids)
        sql += " AND category IN (" + placeholders + ")"
        parameters.extend(category_ids)
    if city and city != "همه شهرها":
        sql += " AND city = ?"
        parameters.append(city)
    if use_nearby:
        sql += " AND latitude IS NOT NULL AND longitude IS NOT NULL"
        delta_lat = radius_km / 111.0
        cos_lat = max(0.01, abs(math.cos(math.radians(near_lat))))
        delta_lon = radius_km / (111.0 * cos_lat)
        sql += " AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
        parameters.extend([
            near_lat - delta_lat, near_lat + delta_lat,
            near_lon - delta_lon, near_lon + delta_lon,
        ])
    if before_id is not None and before_id > 0 and not use_nearby:
        # Stable keyset under (featured DESC, id DESC): next page has smaller id among same rank band.
        sql += " AND id < ?"
        parameters.append(before_id)

    # Fetch one extra row to detect has_more without a separate COUNT(*).
    fetch_limit = page_size + 1 if not use_nearby else min(300, page_size * 3)
    sql += " ORDER BY featured DESC, id DESC LIMIT ?"
    parameters.append(fetch_limit)

    with get_connection() as connection:
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "UPDATE listings SET featured=0 WHERE featured=1 AND featured_until<>'' AND featured_until<?",
            (now,),
        )
        try:
            rows = connection.execute(sql, parameters).fetchall()
        except Exception:
            # If FTS is unavailable on a legacy DB, fall back to bounded LIKE once.
            if fts_match:
                fallback_sql = "SELECT * FROM listings WHERE 1=1"
                fallback_params: list[Any] = []
                term = f"%{query}%"
                fallback_sql += " AND (title LIKE ? OR description LIKE ? OR city LIKE ?)"
                fallback_params.extend([term, term, term])
                if category and category != "all":
                    category_ids = list(dict.fromkeys([category, *CATEGORY_GROUPS.get(category, [])]))
                    placeholders = ",".join("?" for _ in category_ids)
                    fallback_sql += " AND category IN (" + placeholders + ")"
                    fallback_params.extend(category_ids)
                if city and city != "همه شهرها":
                    fallback_sql += " AND city = ?"
                    fallback_params.append(city)
                fallback_sql += " ORDER BY featured DESC, id DESC LIMIT ?"
                fallback_params.append(fetch_limit)
                rows = connection.execute(fallback_sql, fallback_params).fetchall()
            else:
                raise

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
        page = items[:page_size]
        return jsonify({
            "items": page,
            "count": len(page),
            "nearby": True,
            "radius_km": radius_km,
            "has_more": len(items) > page_size,
            "next_before_id": None,
        })

    has_more = len(items) > page_size
    page = items[:page_size]
    next_before_id = page[-1]["id"] if has_more and page else None
    return jsonify({
        "items": page,
        "count": len(page),
        "nearby": False,
        "radius_km": None,
        "has_more": has_more,
        "next_before_id": next_before_id,
    })

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
    if not isinstance(category, str) or category not in CATEGORY_ALLOWED_IDS:
        return jsonify({"error": "invalid_category"}), 400
    if not isinstance(city, str) or not city.strip() or len(city.strip()) > 100:
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
            if not isinstance(category, str) or category not in CATEGORY_ALLOWED_IDS:
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

