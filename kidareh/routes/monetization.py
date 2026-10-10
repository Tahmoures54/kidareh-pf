from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from ..core import current_user, csrf_valid, get_connection

bp = Blueprint("monetization", __name__)

PACKAGES = [
    {"id": "trial_boost_3d", "name": "شروع دیده‌شدن", "price": 9000, "days": 3, "icon": "✨", "tag": "شروع کم‌هزینه", "description": "اولویت موقت نمایش کالاها در نتایج مرتبط.", "features": ["اولویت نمایش کالاها", "مناسب برای آزمودن تبلیغ"]},
    {"id": "search_boost_7d", "name": "نشان ویژه جست‌وجو", "price": 49000, "days": 7, "icon": "🚀", "tag": "پیشنهاد محبوب", "description": "نمایش برجسته‌تر کالاهای فروشگاه در بازه هفت‌روزه.", "features": ["اولویت نمایش کالاها", "مدت ۷ روز"]},
    {"id": "search_boost_30d", "name": "نشان ویژه جست‌وجو", "price": 149000, "days": 30, "icon": "📈", "tag": "یک‌ماهه", "description": "یک ماه فرصت بیشتر برای دیده‌شدن کالاها.", "features": ["اولویت نمایش کالاها", "مدت ۳۰ روز"]},
    {"id": "market_story_1d", "name": "استوری بازار", "price": 19000, "days": 1, "icon": "📣", "tag": "۲۴ ساعته", "description": "معرفی ویترین در جایگاه استوری بازار شهر.", "features": ["جایگاه معرفی محلی", "مدت ۲۴ ساعت"]},
    {"id": "market_story_7d", "name": "استوری بازار", "price": 89000, "days": 7, "icon": "📣", "tag": "۷ روزه", "description": "معرفی ویترین در جایگاه استوری بازار شهر.", "features": ["جایگاه معرفی محلی", "مدت ۷ روز"]},
    {"id": "homepage_banner_7d", "name": "بنر فروشگاه", "price": 99000, "days": 7, "icon": "🖼️", "tag": "تبلیغ محلی", "description": "درخواست حضور فروشگاه در جایگاه بنر شهر؛ با برچسب تبلیغ.", "features": ["جایگاه بنر تبلیغاتی", "مدت ۷ روز"]},
    {"id": "visibility_bundle_7d", "name": "بسته دیده‌شدن", "price": 149000, "days": 7, "icon": "🌟", "tag": "بسته ترکیبی", "description": "ترکیبی از اولویت جست‌وجو و جایگاه‌های معرفی محلی.", "features": ["اولویت نمایش کالاها", "استوری و بنر محلی", "مدت ۷ روز"]},
    {"id": "blue_tick_30d", "name": "تیک آبی فروشگاه", "price": 79000, "days": 30, "icon": "☑️", "tag": "اعتماد بیشتر", "description": "نشان زمان‌دار فروشگاه. این نشان به‌تنهایی به معنی ضمانت کی‌داره نیست.", "features": ["نمایش نشان کنار ویترین", "مدت ۳۰ روز"]},
]

TAG_PACKAGES = [
    {"id": "listing_tag_sale", "name": "تگ حراج", "price": 19000, "days": 7, "icon": "🔥", "tag": "جلب توجه", "label": "حراج", "description": "برای کالایی که می‌خواهید با پیشنهاد قیمتی جذاب‌تر معرفی کنید.", "features": ["نمایش تگ روی همان کالا", "اعتبار ۷ روزه", "حذف خودکار پس از پایان اعتبار"]},
    {"id": "listing_tag_special", "name": "تگ فروش ویژه", "price": 29000, "days": 7, "icon": "⭐", "tag": "ویژه", "label": "فروش ویژه", "description": "کالای منتخب خود را با یک نشان واضح و چشم‌گیر معرفی کنید.", "features": ["نمایش تگ روی همان کالا", "اعتبار ۷ روزه", "حذف خودکار پس از پایان اعتبار"]},
    {"id": "listing_tag_discount", "name": "تگ تخفیف‌دار", "price": 15000, "days": 7, "icon": "％", "tag": "اقتصادی", "label": "تخفیف‌دار", "description": "به خریدار نشان دهید برای این کالا تخفیف در نظر گرفته‌اید.", "features": ["نمایش تگ روی همان کالا", "اعتبار ۷ روزه", "حذف خودکار پس از پایان اعتبار"]},
]
TAG_LABELS = {p["id"]: p["label"] for p in TAG_PACKAGES}

def ensure_tables():
    with get_connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS monetization_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, store_id INTEGER NOT NULL,
            package_id TEXT NOT NULL, listing_id INTEGER, amount_toman INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            gateway_ref TEXT NOT NULL DEFAULT '', gateway_code TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, paid_at TEXT NOT NULL DEFAULT ''
            )""")
        order_columns = {r["name"] for r in db.execute("PRAGMA table_info(monetization_orders)")}
        if "listing_id" not in order_columns:
            db.execute("ALTER TABLE monetization_orders ADD COLUMN listing_id INTEGER")
        db.execute("""CREATE TABLE IF NOT EXISTS listing_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            tag_type TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', order_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_tags_order ON listing_tags(order_id)")
        db.execute("UPDATE listing_tags SET status='expired' WHERE status='active' AND ends_at<?", (datetime.now(timezone.utc).isoformat(),))
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_monetization_gateway_ref ON monetization_orders(gateway_ref) WHERE gateway_ref <> ''")
        db.execute("""CREATE TABLE IF NOT EXISTS store_promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, store_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            package_id TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        columns = {r["name"] for r in db.execute("PRAGMA table_info(stores)")}
        if "badge_until" not in columns:
            db.execute("ALTER TABLE stores ADD COLUMN badge_until TEXT NOT NULL DEFAULT ''")
        listing_columns = {r["name"] for r in db.execute("PRAGMA table_info(listings)")}
        if "featured_until" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN featured_until TEXT NOT NULL DEFAULT ''")
        now = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE listings SET featured=0 WHERE featured=1 AND featured_until<>'' AND featured_until<?", (now,))
        db.execute("UPDATE store_promotions SET status='expired' WHERE status='active' AND ends_at<?", (now,))

ZIBAL_REQUEST_URL = "https://gateway.zibal.ir/v1/request"
ZIBAL_VERIFY_URL = "https://gateway.zibal.ir/v1/verify"
ZIBAL_START_URL = "https://gateway.zibal.ir/start"


def zibal_merchant() -> str:
    return os.environ.get("ZIBAL_MERCHANT", "").strip() or os.environ.get("ZIBAL_MERCHANT_ID", "").strip()


def zibal_request(url: str, payload: dict) -> dict:
    merchant = zibal_merchant()
    if not merchant:
        raise RuntimeError("درگاه زیبال پیکربندی نشده است. متغیر ZIBAL_MERCHANT را در تنظیمات سرور ثبت کنید.")
    body = json.dumps({"merchant": merchant, **payload}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        current_app.logger.warning("Zibal request failed (%s): %s", exc.code, detail)
        raise RuntimeError("زیبال درخواست پرداخت را نپذیرفت؛ لطفاً بعداً تلاش کنید.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        current_app.logger.warning("Zibal connection/response error: %s", exc)
        raise RuntimeError("ارتباط با درگاه زیبال برقرار نشد.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("پاسخ نامعتبر از درگاه زیبال دریافت شد.")
    return data

@bp.get("/monetization")
def monetization_page():
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("pages/seller/monetization.html", csrf_token=session["csrf_token"], packages=PACKAGES)

@bp.get("/api/monetization/packages")
def packages():
    return jsonify({"items": PACKAGES + TAG_PACKAGES, "tag_items": TAG_PACKAGES, "currency": "تومان", "payment_enabled": bool(zibal_merchant())})

@bp.get("/api/my/listings")
def my_listings_for_tags():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    ensure_tables()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as db:
        rows = db.execute(
            """SELECT l.id, l.title, l.price, l.city,
                      (SELECT lt.tag_type FROM listing_tags lt WHERE lt.listing_id=l.id AND lt.status='active' AND lt.ends_at>? ORDER BY lt.ends_at DESC LIMIT 1) AS active_tag,
                      (SELECT lt.ends_at FROM listing_tags lt WHERE lt.listing_id=l.id AND lt.status='active' AND lt.ends_at>? ORDER BY lt.ends_at DESC LIMIT 1) AS tag_ends_at
               FROM listings l WHERE l.owner_id=? ORDER BY l.id DESC LIMIT 100""",
            (now, now, user["id"]),
        ).fetchall()
    return jsonify({"items": [dict(row) for row in rows], "tag_labels": TAG_LABELS})


@bp.get("/api/monetization/orders")
def my_orders():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    ensure_tables()
    with get_connection() as db:
        rows = db.execute("SELECT id, package_id, amount_toman, status, created_at, paid_at FROM monetization_orders WHERE user_id=? ORDER BY id DESC LIMIT 30", (user["id"],)).fetchall()
    return jsonify({"items": [dict(r) for r in rows]})

@bp.post("/api/monetization/orders")
def create_order():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای خرید بسته وارد حساب فروشنده شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    ensure_tables()
    payload = request.get_json(silent=True) or {}
    all_packages = PACKAGES + TAG_PACKAGES
    package = next((p for p in all_packages if p["id"] == payload.get("package_id")), None)
    if not package:
        return jsonify({"error": "invalid_package", "message": "بسته انتخاب‌شده معتبر نیست."}), 400
    if not zibal_merchant():
        return jsonify({"error": "payment_unavailable", "message": "درگاه زیبال پیکربندی نشده است."}), 503
    listing_id = payload.get("listing_id")
    is_listing_tag = package["id"] in TAG_LABELS
    with get_connection() as db:
        store = db.execute("SELECT id FROM stores WHERE owner_id=?", (user["id"],)).fetchone()
        if not store:
            return jsonify({"error": "store_required", "message": "ابتدا از بخش ویترین من، فروشگاه خود را بسازید."}), 409
        if is_listing_tag:
            try:
                listing_id = int(listing_id)
            except (TypeError, ValueError):
                return jsonify({"error": "listing_required", "message": "ابتدا کالایی را که می‌خواهید تگ بخورد انتخاب کنید."}), 400
            listing = db.execute("SELECT id, store_id FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
            if not listing:
                return jsonify({"error": "listing_forbidden", "message": "فقط می‌توانید برای کالای خودتان تگ بخرید."}), 403
            if not listing["store_id"]:
                return jsonify({"error": "store_required", "message": "کالا باید به ویترین فروشگاه شما متصل باشد."}), 409
            store_id = listing["store_id"]
        else:
            listing_id = None
            store_id = store["id"]
        cursor = db.execute(
            "INSERT INTO monetization_orders (user_id, store_id, package_id, listing_id, amount_toman, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (user["id"], store_id, package["id"], listing_id, package["price"]),
        )
        order_id = cursor.lastrowid
    callback_url = url_for("monetization.payment_callback", order_id=order_id, _external=True)
    try:
        result = zibal_request(ZIBAL_REQUEST_URL, {
            "amount": package["price"] * 10,
            "callbackUrl": callback_url,
            "orderId": f"kidareh-{order_id}",
            "description": f"خرید {package['name']} از کی‌داره - سفارش {order_id}",
            "mobile": user["phone"],
        })
        track_id = str(result.get("trackId", "")).strip()
        if result.get("result") != 100 or not track_id:
            raise RuntimeError(str(result.get("message") or "درخواست پرداخت در زیبال ناموفق بود."))
        with get_connection() as db:
            db.execute("UPDATE monetization_orders SET gateway_code=? WHERE id=? AND status='pending'", (track_id, order_id))
        return jsonify({
            "success": True,
            "order_id": order_id,
            "redirect_url": f"{ZIBAL_START_URL}/{track_id}",
        })
    except RuntimeError as exc:
        with get_connection() as db:
            db.execute("UPDATE monetization_orders SET status='failed' WHERE id=? AND status='pending'", (order_id,))
        return jsonify({"error": "payment_unavailable", "message": str(exc)}), 503


@bp.get("/monetization/callback")
def payment_callback():
    ensure_tables()
    order_id = request.args.get("order_id", type=int)
    track_id = (request.args.get("trackId") or request.args.get("trackid") or "").strip()
    success = request.args.get("success")
    status = request.args.get("status")
    if success == "0" or status == "3":
        return redirect(url_for("monetization.monetization_page", payment="cancelled"))
    if not order_id or not track_id or not track_id.isdigit():
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    with get_connection() as db:
        order = db.execute("SELECT * FROM monetization_orders WHERE id=?", (order_id,)).fetchone()
    if not order or order["status"] != "pending" or str(order["gateway_code"]) != track_id:
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    package = next((p for p in PACKAGES + TAG_PACKAGES if p["id"] == order["package_id"]), None)
    if not package:
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    try:
        result = zibal_request(ZIBAL_VERIFY_URL, {"trackId": int(track_id)})
    except RuntimeError:
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    if result.get("result") not in (100, 201):
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    # Do not grant paid features unless the gateway explicitly confirms both
    # the exact amount (Rials) and the merchant-generated order ID.
    verified_amount = result.get("amount")
    if (
        isinstance(verified_amount, bool)
        or not isinstance(verified_amount, (int, str))
        or not str(verified_amount).isdigit()
        or int(verified_amount) != int(order["amount_toman"]) * 10
    ):
        current_app.logger.warning("Zibal amount missing/invalid/mismatched for monetization order %s", order_id)
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    expected_order_id = f"kidareh-{order_id}"
    verified_order_id = result.get("orderId")
    if not isinstance(verified_order_id, (str, int)) or str(verified_order_id) != expected_order_id:
        current_app.logger.warning("Zibal order ID missing/invalid/mismatched for monetization order %s", order_id)
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    now = datetime.now(timezone.utc)
    starts = now.isoformat()
    ends = (now + timedelta(days=package["days"])).isoformat()
    ref_id = str(result.get("refNumber") or track_id)
    with get_connection() as db:
        updated = db.execute(
            "UPDATE monetization_orders SET status='paid', gateway_ref=?, paid_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending' AND gateway_code=?",
            (ref_id, order_id, track_id),
        )
        if updated.rowcount != 1:
            return redirect(url_for("monetization.monetization_page", payment="unverified"))
        if package["id"] in TAG_LABELS:
            if not order["listing_id"]:
                db.execute("UPDATE monetization_orders SET status='failed' WHERE id=?", (order_id,))
                return redirect(url_for("monetization.monetization_page", payment="unverified"))
            db.execute("UPDATE listing_tags SET status='replaced' WHERE listing_id=? AND status='active'", (order["listing_id"],))
            db.execute(
                "INSERT INTO listing_tags (listing_id,user_id,tag_type,starts_at,ends_at,status,order_id) VALUES (?,?,?,?,?,'active',?)",
                (order["listing_id"], order["user_id"], package["id"], starts, ends, order_id),
            )
        else:
            db.execute(
                "INSERT INTO store_promotions (store_id,user_id,package_id,starts_at,ends_at,status) VALUES (?,?,?,?,?,'active')",
                (order["store_id"], order["user_id"], package["id"], starts, ends),
            )
        if package["id"] == "blue_tick_30d":
            db.execute("UPDATE stores SET badge_until=? WHERE id=?", (ends, order["store_id"]))
        if package["id"] in ("trial_boost_3d", "search_boost_7d", "search_boost_30d", "visibility_bundle_7d"):
            db.execute("UPDATE listings SET featured=1, featured_until=? WHERE store_id=?", (ends, order["store_id"]))
    return redirect(url_for("pages.seller_tags_page", payment="success") if package["id"] in TAG_LABELS else url_for("monetization.monetization_page", payment="success"))

@bp.get("/api/monetization/status")
def monetization_status():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    ensure_tables()
    with get_connection() as db:
        store = db.execute("SELECT id, badge_until FROM stores WHERE owner_id=?", (user["id"],)).fetchone()
        promos = db.execute("SELECT package_id, ends_at FROM store_promotions WHERE user_id=? AND status='active' AND ends_at>CURRENT_TIMESTAMP ORDER BY ends_at DESC", (user["id"],)).fetchall()
    return jsonify({"store": dict(store) if store else None, "promotions": [dict(p) for p in promos]})


@bp.get("/api/monetization/sponsored")
def sponsored_stores():
    ensure_tables()
    city = request.args.get("city", "").strip()[:60]
    now = datetime.now(timezone.utc).isoformat()
    promo_ids = ("market_story_1d", "market_story_7d", "homepage_banner_7d", "visibility_bundle_7d")
    placeholders = ",".join("?" for _ in promo_ids)
    sql = f"""SELECT s.id, s.name, s.city, s.description, p.package_id, p.ends_at
              FROM store_promotions p JOIN stores s ON s.id=p.store_id
              WHERE p.status='active' AND p.ends_at>? AND p.package_id IN ({placeholders})"""
    args = [now, *promo_ids]
    if city:
        sql += " AND s.city=?"
        args.append(city)
    sql += " ORDER BY p.created_at DESC LIMIT 12"
    with get_connection() as db:
        rows = db.execute(sql, args).fetchall()
    labels = {
        "market_story_1d": "استوری بازار · تبلیغ",
        "market_story_7d": "استوری بازار · تبلیغ",
        "homepage_banner_7d": "بنر محلی · تبلیغ",
        "visibility_bundle_7d": "معرفی ویژه · تبلیغ",
    }
    return jsonify({"items": [{**dict(row), "placement_label": labels.get(row["package_id"], "تبلیغ")} for row in rows]})
