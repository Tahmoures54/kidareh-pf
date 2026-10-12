import hashlib
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from ..core import current_user, csrf_valid, get_connection
from ..data_catalog import is_city_name, normalize_location_name
from ..services.sms import send_otp

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

PHONE_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def ensure_tables() -> None:
    """Create the shared OTP rate-limit ledger once, during start-up.

    The ledger used to be created inside the request that first needed it, which
    ran schema DDL while serving a login attempt.
    """
    with get_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS otp_rate_limits (
                scope TEXT NOT NULL, key_hash TEXT NOT NULL, last_sent_at REAL NOT NULL DEFAULT 0,
                window_started_at REAL NOT NULL DEFAULT 0, request_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scope, key_hash)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS otp_challenges (
                id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                terms_accepted_at TEXT NOT NULL,
                existing_user INTEGER NOT NULL DEFAULT 0,
                consumed_at REAL,
                created_at REAL NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_otp_challenges_phone_created ON otp_challenges(phone, created_at)"
        )


def _normalize_phone(value):
    if not isinstance(value, str):
        return None
    phone = re.sub(r"[\s()\-]", "", value.translate(PHONE_TRANSLATION))
    return phone if re.fullmatch(r"09\d{9}", phone) else None


def _send_kavenegar_otp(phone, code):
    """Compatibility wrapper for tests and the existing OTP route."""
    return send_otp(phone, code)


def _check_otp_rate_limit(phone):
    """Enforce shared SQLite rate limits across sessions and app workers."""
    now = time.time()
    ip = request.remote_addr or "unknown"
    keys = {
        "phone": hashlib.sha256(phone.encode("utf-8")).hexdigest(),
        "ip": hashlib.sha256(ip.encode("utf-8")).hexdigest(),
    }
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = {}
        for scope, key_hash in keys.items():
            row = connection.execute("SELECT last_sent_at, window_started_at, request_count FROM otp_rate_limits WHERE scope=? AND key_hash=?", (scope, key_hash)).fetchone()
            rows[scope] = dict(row) if row else {"last_sent_at": 0, "window_started_at": now, "request_count": 0}
        phone_row, ip_row = rows["phone"], rows["ip"]
        if now - phone_row["last_sent_at"] < 60:
            return False, "otp_cooldown", max(1, int(60 - (now - phone_row["last_sent_at"])))
        if now - phone_row["window_started_at"] >= 3600:
            phone_row.update(window_started_at=now, request_count=0)
        if now - ip_row["window_started_at"] >= 3600:
            ip_row.update(window_started_at=now, request_count=0)
        if phone_row["request_count"] >= 3:
            return False, "otp_hourly_limit", max(1, int(3600 - (now - phone_row["window_started_at"])))
        if ip_row["request_count"] >= 10:
            return False, "otp_ip_limit", max(1, int(3600 - (now - ip_row["window_started_at"])))
        for scope, key_hash in keys.items():
            row = rows[scope]
            connection.execute("""INSERT INTO otp_rate_limits(scope,key_hash,last_sent_at,window_started_at,request_count)
                VALUES(?,?,?,?,?) ON CONFLICT(scope,key_hash) DO UPDATE SET
                last_sent_at=excluded.last_sent_at, window_started_at=excluded.window_started_at,
                request_count=excluded.request_count""",
                (scope, key_hash, now, row["window_started_at"], row["request_count"] + 1))
    return True, "", 0


@bp.get("/challenge")
def auth_challenge():
    left, right = secrets.randbelow(8) + 2, secrets.randbelow(8) + 1
    session["math_challenge_answer"] = str(left + right)
    session["math_challenge_at"] = time.time()
    return jsonify({"question": f"{left} + {right} = ؟"})


@bp.post("/request-otp")
def request_otp():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    payload = request.get_json(silent=True) or {}
    phone = _normalize_phone(payload.get("phone"))
    # `registering` is accepted for API compatibility; the account itself is
    # always created by /complete-profile after the phone is verified.
    requested_role = payload.get("role", "seller")
    if requested_role not in {"buyer", "seller"}:
        return jsonify({"error": "invalid_role", "message": "نوع حساب معتبر نیست."}), 400
    if not phone:
        return jsonify({"error": "invalid_phone", "message": "شماره همراه باید مانند 09123456789 باشد."}), 400
    answer = payload.get("captcha_answer", "")
    answer = answer.translate(PHONE_TRANSLATION).strip() if isinstance(answer, str) else str(answer)
    if time.time() - session.get("math_challenge_at", 0) > 300 or not secrets.compare_digest(answer, str(session.get("math_challenge_answer", "!"))):
        return jsonify({"error": "captcha_failed", "message": "پاسخ محاسبه درست نیست؛ دوباره تلاش کنید."}), 400
    session.pop("math_challenge_answer", None)
    session.pop("math_challenge_at", None)
    # Continuing after the clearly displayed terms notice records acceptance;
    # no separate checkbox is required for the SMS-only authentication flow.
    allowed, limit_error, retry_after = _check_otp_rate_limit(phone)
    if not allowed:
        message = "برای ارسال دوباره کد کمی صبر کنید." if limit_error == "otp_cooldown" else "سقف درخواست پیامک موقتاً پر شده است؛ بعداً دوباره تلاش کنید."
        return jsonify({"error": limit_error, "message": message, "retry_after": retry_after}), 429
    with get_connection() as connection:
        exists = connection.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone() is not None
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        _send_kavenegar_otp(phone, code)
    except Exception as exc:
        # Log safe diagnostic fields only (no API key / no full URL).
        reason = getattr(exc, "reason", None) or type(exc).__name__
        detail = str(exc)[:200] if str(exc) else type(exc).__name__
        if "api.kavenegar.com" in detail:
            detail = reason
        current_app.logger.error(
            "Kavenegar OTP delivery failed reason=%s detail=%s",
            reason,
            detail,
        )
        return jsonify({"error": "sms_unavailable", "message": "ارسال پیامک ممکن نشد. تنظیمات یا سرویس پیامک را بررسی کنید."}), 503
    challenge_id = uuid.uuid4().hex
    accepted_at = datetime.now(timezone.utc).isoformat()
    now = time.time()
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO otp_challenges
               (id, phone, otp_hash, expires_at, attempts, terms_accepted_at, existing_user, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
            (challenge_id, phone, generate_password_hash(code), now + 300, accepted_at, int(exists), now),
        )
    # Only the opaque challenge ID stays in the signed browser session; the OTP
    # hash, phone, expiry, attempt count, and acceptance timestamp remain server-side.
    session.pop("otp_phone", None)
    session.pop("otp_hash", None)
    session.pop("otp_expires_at", None)
    session.pop("otp_attempts", None)
    session["otp_challenge_id"] = challenge_id
    result = {"ok": True, "message": "کد تأیید ارسال شد.", "expires_in": 300}
    if current_app.testing and current_app.config.get("TESTING_OTP_CODE"):
        result["test_code"] = code
    return jsonify(result)


@bp.post("/verify-otp")
def verify_otp():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    payload = request.get_json(silent=True) or {}
    code = payload.get("code", "")
    code = code.translate(PHONE_TRANSLATION).strip() if isinstance(code, str) else str(code)
    challenge_id = session.get("otp_challenge_id")
    if not isinstance(challenge_id, str) or not challenge_id:
        return jsonify({"error": "otp_expired", "message": "کد منقضی شده است؛ دوباره درخواست کد کنید."}), 400

    now = time.time()
    with get_connection() as connection:
        # Serialize attempts and consumption so parallel requests cannot reuse a
        # valid OTP or bypass the maximum number of guesses.
        connection.execute("BEGIN IMMEDIATE")
        challenge = connection.execute(
            """SELECT id, phone, otp_hash, expires_at, attempts, terms_accepted_at
               FROM otp_challenges WHERE id = ? AND consumed_at IS NULL""",
            (challenge_id,),
        ).fetchone()
        if not challenge or now > challenge["expires_at"]:
            connection.execute(
                "UPDATE otp_challenges SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL",
                (now, challenge_id),
            )
            session.pop("otp_challenge_id", None)
            return jsonify({"error": "otp_expired", "message": "کد منقضی شده است؛ دوباره درخواست کد کنید."}), 400

        if challenge["attempts"] >= 5:
            connection.execute(
                "UPDATE otp_challenges SET consumed_at = ? WHERE id = ?",
                (now, challenge_id),
            )
            session.pop("otp_challenge_id", None)
            return jsonify({"error": "otp_locked", "message": "تعداد تلاش‌ها تمام شد؛ کد تازه درخواست کنید."}), 429

        if not check_password_hash(challenge["otp_hash"], code):
            attempts = challenge["attempts"] + 1
            connection.execute(
                "UPDATE otp_challenges SET attempts = ?, consumed_at = ? WHERE id = ?",
                (attempts, now if attempts >= 5 else None, challenge_id),
            )
            if attempts >= 5:
                session.pop("otp_challenge_id", None)
                return jsonify({"error": "otp_locked", "message": "تعداد تلاش‌ها تمام شد؛ کد تازه درخواست کنید."}), 429
            return jsonify({"error": "otp_invalid", "message": "کد تأیید نادرست است."}), 400

        phone = challenge["phone"]
        accepted_at = challenge["terms_accepted_at"]
        connection.execute(
            "UPDATE otp_challenges SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL",
            (now, challenge_id),
        )
        user = connection.execute(
            "SELECT id, name, phone, role, is_banned FROM users WHERE phone = ?",
            (phone,),
        ).fetchone()
        if user and user["is_banned"]:
            session.pop("otp_challenge_id", None)
            return jsonify({"error": "account_banned", "message": "حساب کاربری شما مسدود شده است."}), 403
        if user:
            connection.execute(
                "UPDATE users SET phone_verified_at = COALESCE(NULLIF(phone_verified_at, ''), ?), "
                "terms_accepted_at = COALESCE(NULLIF(terms_accepted_at, ''), ?) WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), accepted_at or "", user["id"]),
            )

    session.pop("otp_challenge_id", None)
    if user:
        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = uuid.uuid4().hex
        return jsonify({"existing_user": True, "user": {"id": user["id"], "name": user["name"], "phone": user["phone"], "role": user["role"]}, "csrf_token": session["csrf_token"]})

    # An unknown phone is never auto-registered: profile completion creates the account.
    session["verified_phone"] = phone
    session["verified_terms_accepted_at"] = accepted_at
    return jsonify({"existing_user": False, "phone": phone})


@bp.post("/complete-profile")
def complete_profile():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    phone = session.get("verified_phone")
    accepted_at = session.get("verified_terms_accepted_at")
    if not phone or not accepted_at:
        return jsonify({"error": "phone_verification_required", "message": "ابتدا شماره همراه را تأیید کنید."}), 401
    payload = request.get_json(silent=True) or {}
    name, role = payload.get("name", ""), payload.get("role", "buyer")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "invalid_name", "message": "نام و نام خانوادگی را وارد کنید."}), 400
    if role not in {"buyer", "seller"}:
        return jsonify({"error": "invalid_role", "message": "نوع حساب معتبر نیست."}), 400
    store = None
    values = {}
    profile_city = normalize_location_name(payload.get("city", ""))
    if role == "buyer" and not is_city_name(profile_city):
        return jsonify({"error": "invalid_city", "message": "شهر محل سکونت را از فهرست شهرهای معتبر انتخاب کنید."}), 400
    if role == "seller":
        values = {
            "name": payload.get("store_name", ""), "category": payload.get("store_category", ""),
            "city": normalize_location_name(payload.get("store_city", "")), "contact_name": payload.get("contact_name", name.strip()),
            "address": payload.get("store_address", ""), "hours": payload.get("store_hours", ""),
            "description": payload.get("store_description", ""),
            "in_person": 1 if payload.get("in_person") else 0,
        }
        if not isinstance(values["name"], str) or not values["name"].strip() or len(values["name"].strip()) > 80:
            return jsonify({"error": "invalid_store_name", "message": "نام فروشگاه را وارد کنید."}), 400
        if not values["city"] or len(values["city"]) > 60 or not is_city_name(values["city"]):
            return jsonify({"error": "invalid_store_city", "message": "شهر فروشگاه را از فهرست شهرهای معتبر انتخاب کنید."}), 400
        if not isinstance(values["category"], str) or len(values["category"].strip()) > 80:
            return jsonify({"error": "invalid_store_details", "message": "صنف فروشگاه معتبر نیست."}), 400
        raw_lat, raw_lng = payload.get("latitude"), payload.get("longitude")
        try:
            if raw_lat in (None, "") and raw_lng in (None, ""):
                values["latitude"], values["longitude"] = None, None
            else:
                values["latitude"], values["longitude"] = float(raw_lat), float(raw_lng)
                if not (-90 <= values["latitude"] <= 90 and -180 <= values["longitude"] <= 180):
                    raise ValueError("coordinates out of range")
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_coordinates", "message": "مختصات فروشگاه معتبر نیست؛ دوباره موقعیت را دریافت کنید."}), 400
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at, terms_accepted_at, city) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), phone, generate_password_hash(secrets.token_urlsafe(32)), role, datetime.now(timezone.utc).isoformat(), accepted_at, profile_city if role == "buyer" else values["city"]),
            )
            user_id = cursor.lastrowid
            if role == "seller":
                store_cursor = connection.execute(
                    """INSERT INTO stores
                       (owner_id, name, city, description, category, contact_name, address, hours, in_person, latitude, longitude)
                       VALUES (?, ?, ?, '', ?, ?, '', '', 1, ?, ?)""",
                    (user_id, values["name"].strip(), values["city"].strip(), values["category"].strip(),
                     values["contact_name"].strip(), values["latitude"], values["longitude"]),
                )
                store = dict(connection.execute("SELECT * FROM stores WHERE id = ?", (store_cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError:
        return jsonify({"error": "phone_exists", "message": "این شماره قبلاً ثبت شده است؛ کد ورود را دوباره درخواست کنید."}), 409
    session.clear()
    session["user_id"] = user_id
    session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": {"id": user_id, "name": name.strip(), "phone": phone, "role": role, "city": profile_city if role == "buyer" else values["city"]}, "store": store, "csrf_token": session["csrf_token"]})


@bp.post("/signup")
def auth_signup():
    """Reject legacy password signup so mobile verification cannot be bypassed."""
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    return jsonify({
        "error": "otp_required",
        "message": "ثبت‌نام فقط پس از تأیید کد پیامکی امکان‌پذیر است.",
        "next": "/api/auth/request-otp",
    }), 410

@bp.post("/login")
def auth_login():
    """Legacy password login is intentionally disabled: SMS OTP is the only login method."""
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    return jsonify({
        "error": "sms_login_only",
        "message": "ورود به کی‌داره فقط با کد یک‌بارمصرف پیامکی انجام می‌شود.",
        "next": "/api/auth/request-otp",
    }), 410

@bp.post("/become-seller")
def become_seller():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required"}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    with get_connection() as connection:
        connection.execute("UPDATE users SET role = 'seller' WHERE id = ?", (user["id"],))
        has_store = connection.execute("SELECT 1 FROM stores WHERE owner_id = ?", (user["id"],)).fetchone() is not None
    user["role"] = "seller"
    response = {
        "user": user,
        "has_store": has_store,
        "message": "حساب شما به فروشنده تغییر کرد." if has_store else "حساب شما به فروشنده تغییر کرد. برای افزودن کالا ابتدا ویترین فروشگاه را بسازید.",
        "next": None if has_store else "/api/stores",
    }
    return jsonify(response)

@bp.get("/me")
def auth_me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    if not session.get("csrf_token"):
        session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": user, "csrf_token": session["csrf_token"]})

@bp.post("/logout")
def auth_logout():
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    session.clear()
    return jsonify({"ok": True})


@bp.post("/profile")
def update_profile():
    """Update the signed-in user's basic profile without changing verified identity."""
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "ابتدا وارد حساب شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed", "message": "صفحه را تازه‌سازی کنید و دوباره تلاش کنید."}), 400
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "invalid_name", "message": "نام و نام خانوادگی را وارد کنید."}), 400
    name = name.strip()
    with get_connection() as connection:
        connection.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
        row = connection.execute("SELECT id, name, phone, role FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({"ok": True, "user": dict(row)})
