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

def ensure_tables():
    with get_connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS monetization_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, store_id INTEGER NOT NULL,
            package_id TEXT NOT NULL, amount_toman INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            gateway_ref TEXT NOT NULL DEFAULT '', gateway_code TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, paid_at TEXT NOT NULL DEFAULT ''
            )""")
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

def gateway_request(path: str, payload: dict):
    token = os.environ.get("PAYPING_TOKEN", "").strip()
    if not token:
        raise RuntimeError("درگاه پرداخت هنوز پیکربندی نشده است. متغیر PAYPING_TOKEN باید در تنظیمات سرور ثبت شود.")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.payping.ir/v2/" + path.lstrip("/"), data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        current_app.logger.warning("PayPing %s failed (%s): %s", path, exc.code, detail)
        raise RuntimeError("درگاه پرداخت درخواست را نپذیرفت؛ لطفاً بعداً دوباره تلاش کنید.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        current_app.logger.warning("PayPing connection error: %s", exc)
        raise RuntimeError("ارتباط با درگاه پرداخت برقرار نشد.") from exc

@bp.get("/monetization")
def monetization_page():
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("pages/seller/monetization.html", csrf_token=session["csrf_token"], packages=PACKAGES)

@bp.get("/api/monetization/packages")
def packages():
    return jsonify({"items": PACKAGES, "currency": "تومان", "payment_enabled": bool(os.environ.get("PAYPING_TOKEN", "").strip())})

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
    package = next((p for p in PACKAGES if p["id"] == payload.get("package_id")), None)
    if not package:
        return jsonify({"error": "invalid_package", "message": "بسته انتخاب‌شده معتبر نیست."}), 400
    with get_connection() as db:
        store = db.execute("SELECT id FROM stores WHERE owner_id=?", (user["id"],)).fetchone()
        if not store:
            return jsonify({"error": "store_required", "message": "ابتدا از بخش ویترین من، فروشگاه خود را بسازید."}), 409
        cursor = db.execute("INSERT INTO monetization_orders (user_id, store_id, package_id, amount_toman, status) VALUES (?, ?, ?, ?, 'pending')", (user["id"], store["id"], package["id"], package["price"]))
        order_id = cursor.lastrowid
    try:
        result = gateway_request("pay", {
            "amount": package["price"] * 10,
            "payerIdentity": user["phone"],
            "payerName": user["name"] or "کاربر کی‌داره",
            "description": f"خرید {package['name']} از کی‌داره - سفارش {order_id}",
            "returnUrl": url_for("monetization.payment_callback", order_id=order_id, _external=True),
            "clientRefId": f"KIDAREH-{order_id}",
        })
        code = str(result.get("code", "")).strip()
        if not code:
            raise RuntimeError("درگاه کد پرداخت برنگرداند.")
        with get_connection() as db:
            db.execute("UPDATE monetization_orders SET gateway_code=? WHERE id=?", (code, order_id))
        return jsonify({"success": True, "order_id": order_id, "redirect_url": f"https://api.payping.ir/v2/pay/gotoipg/{code}"})
    except RuntimeError as exc:
        with get_connection() as db:
            db.execute("UPDATE monetization_orders SET status='failed' WHERE id=? AND status='pending'", (order_id,))
        return jsonify({"error": "payment_unavailable", "message": str(exc)}), 503

@bp.get("/monetization/callback")
def payment_callback():
    ensure_tables()
    order_id = request.args.get("order_id", type=int)
    ref_id = (request.args.get("refid") or request.args.get("refId") or "").strip()
    if not order_id or not ref_id:
        return redirect(url_for("monetization.monetization_page", payment="cancelled"))
    with get_connection() as db:
        order = db.execute("SELECT * FROM monetization_orders WHERE id=?", (order_id,)).fetchone()
    if not order or order["status"] != "pending":
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    package = next((p for p in PACKAGES if p["id"] == order["package_id"]), None)
    if not package:
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    try:
        gateway_request("pay/verify", {"refId": ref_id, "amount": int(order["amount_toman"]) * 10})
    except RuntimeError:
        return redirect(url_for("monetization.monetization_page", payment="unverified"))
    now = datetime.now(timezone.utc)
    starts = now.isoformat()
    ends = (now + timedelta(days=package["days"])).isoformat()
    with get_connection() as db:
        updated = db.execute("UPDATE monetization_orders SET status='paid', gateway_ref=?, paid_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (ref_id, order_id))
        if updated.rowcount != 1:
            return redirect(url_for("monetization.monetization_page", payment="unverified"))
        db.execute("INSERT INTO store_promotions (store_id,user_id,package_id,starts_at,ends_at,status) VALUES (?,?,?,?,?,'active')", (order["store_id"], order["user_id"], package["id"], starts, ends))
        if package["id"] == "blue_tick_30d":
            db.execute("UPDATE stores SET badge_until=? WHERE id=?", (ends, order["store_id"]))
        if package["id"] in ("trial_boost_3d", "search_boost_7d", "search_boost_30d", "visibility_bundle_7d"):
            db.execute("UPDATE listings SET featured=1, featured_until=? WHERE store_id=?", (ends, order["store_id"]))
    return redirect(url_for("monetization.monetization_page", payment="success"))

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
