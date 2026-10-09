import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from ..core import current_user, csrf_valid, get_connection

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

PHONE_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _normalize_phone(value):
    if not isinstance(value, str):
        return None
    phone = re.sub(r"[\s()\-]", "", value.translate(PHONE_TRANSLATION))
    return phone if re.fullmatch(r"09\d{9}", phone) else None


def _send_kavenegar_otp(phone, code):
    api_key = os.environ.get("KAVENEGAR_API_KEY", "").strip()
    template = os.environ.get("KAVENEGAR_VERIFY_TEMPLATE", "").strip()
    if not api_key or not template:
        if current_app.testing and current_app.config.get("TESTING_OTP_CODE"):
            return True
        raise RuntimeError("Kavenegar settings are missing")
    url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(api_key, safe='')}/verify/lookup.json"
    body = urllib.parse.urlencode({"receptor": phone, "token": code, "template": template}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("return", {}).get("status") != 200:
        raise RuntimeError("Kavenegar rejected the verification SMS")
    return True


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
    if not phone:
        return jsonify({"error": "invalid_phone", "message": "شماره همراه باید مانند 09123456789 باشد."}), 400
    answer = payload.get("captcha_answer", "")
    answer = answer.translate(PHONE_TRANSLATION).strip() if isinstance(answer, str) else str(answer)
    if time.time() - session.get("math_challenge_at", 0) > 300 or not secrets.compare_digest(answer, str(session.get("math_challenge_answer", "!"))):
        return jsonify({"error": "captcha_failed", "message": "پاسخ محاسبه درست نیست؛ دوباره تلاش کنید."}), 400
    session.pop("math_challenge_answer", None)
    session.pop("math_challenge_at", None)
    if payload.get("terms_accepted") is not True:
        return jsonify({"error": "terms_required", "message": "برای ادامه باید پذیرش قوانین را تأیید کنید."}), 400
    if time.time() - session.get("otp_last_sent_at", 0) < 45:
        return jsonify({"error": "otp_cooldown", "message": "برای ارسال دوباره کد کمی صبر کنید."}), 429
    with get_connection() as connection:
        exists = connection.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone() is not None
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        _send_kavenegar_otp(phone, code)
    except Exception:
        current_app.logger.exception("Kavenegar OTP delivery failed")
        return jsonify({"error": "sms_unavailable", "message": "ارسال پیامک ممکن نشد. تنظیمات یا سرویس پیامک را بررسی کنید."}), 503
    session["otp_phone"] = phone
    session["otp_hash"] = generate_password_hash(code)
    session["otp_expires_at"] = time.time() + 300
    session["otp_attempts"] = 0
    session["otp_last_sent_at"] = time.time()
    session["otp_terms_accepted_at"] = datetime.now(timezone.utc).isoformat()
    session["otp_existing_user"] = exists
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
    if not session.get("otp_phone") or time.time() > session.get("otp_expires_at", 0):
        return jsonify({"error": "otp_expired", "message": "کد منقضی شده است؛ دوباره درخواست کد کنید."}), 400
    attempts = session.get("otp_attempts", 0)
    if attempts >= 5:
        session.pop("otp_hash", None)
        return jsonify({"error": "otp_locked", "message": "تعداد تلاش‌ها تمام شد؛ کد تازه درخواست کنید."}), 429
    if not check_password_hash(session.get("otp_hash", ""), code):
        session["otp_attempts"] = attempts + 1
        return jsonify({"error": "otp_invalid", "message": "کد تأیید نادرست است."}), 400
    phone = session["otp_phone"]
    accepted_at = session.get("otp_terms_accepted_at")
    with get_connection() as connection:
        user = connection.execute("SELECT id, name, phone, role FROM users WHERE phone = ?", (phone,)).fetchone()
        if user:
            connection.execute(
                "UPDATE users SET phone_verified_at = COALESCE(NULLIF(phone_verified_at, ''), ?), terms_accepted_at = COALESCE(NULLIF(terms_accepted_at, ''), ?) WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), accepted_at or "", user["id"]),
            )
    if user:
        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = uuid.uuid4().hex
        return jsonify({"existing_user": True, "user": {"id": user["id"], "name": user["name"], "phone": user["phone"], "role": user["role"]}, "csrf_token": session["csrf_token"]})
    session["verified_phone"] = phone
    session["verified_terms_accepted_at"] = accepted_at
    session.pop("otp_hash", None)
    session.pop("otp_expires_at", None)
    session.pop("otp_attempts", None)
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
    if role == "seller":
        values = {
            "name": payload.get("store_name", ""), "category": payload.get("store_category", ""),
            "city": payload.get("store_city", ""), "contact_name": payload.get("contact_name", name.strip()),
            "address": payload.get("store_address", ""), "hours": payload.get("store_hours", ""),
            "social_url": payload.get("social_url", ""), "description": payload.get("store_description", ""),
            "in_person": 1 if payload.get("in_person") else 0,
        }
        if not isinstance(values["name"], str) or not values["name"].strip() or len(values["name"].strip()) > 80:
            return jsonify({"error": "invalid_store_name", "message": "نام فروشگاه را وارد کنید."}), 400
        if not isinstance(values["city"], str) or not values["city"].strip() or len(values["city"].strip()) > 60:
            return jsonify({"error": "invalid_store_city", "message": "شهر فروشگاه را وارد کنید."}), 400
        for key, limit in (("category", 80), ("contact_name", 80), ("address", 300), ("hours", 120), ("social_url", 200), ("description", 500)):
            if not isinstance(values[key], str) or len(values[key].strip()) > limit:
                return jsonify({"error": "invalid_store_details", "message": "اطلاعات فروشگاه معتبر نیست."}), 400
        if values["social_url"].strip() and not re.match(r"^(https?://|@)[^\s]+$", values["social_url"].strip(), re.I):
            return jsonify({"error": "invalid_social_url", "message": "نشانی شبکه اجتماعی معتبر نیست."}), 400
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, phone, password_hash, role, phone_verified_at, terms_accepted_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name.strip(), phone, generate_password_hash(secrets.token_urlsafe(32)), role, datetime.now(timezone.utc).isoformat(), accepted_at),
            )
            user_id = cursor.lastrowid
            if role == "seller":
                store_cursor = connection.execute(
                    """INSERT INTO stores (owner_id, name, city, description, category, contact_name, address, hours, social_url, in_person)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, values["name"].strip(), values["city"].strip(), values["description"].strip(), values["category"].strip(),
                     values["contact_name"].strip(), values["address"].strip(), values["hours"].strip(), values["social_url"].strip(), values["in_person"]),
                )
                store = dict(connection.execute("SELECT * FROM stores WHERE id = ?", (store_cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError:
        return jsonify({"error": "phone_exists", "message": "این شماره قبلاً ثبت شده است؛ کد ورود را دوباره درخواست کنید."}), 409
    session.clear()
    session["user_id"] = user_id
    session["csrf_token"] = uuid.uuid4().hex
    return jsonify({"user": {"id": user_id, "name": name.strip(), "phone": phone, "role": role}, "store": store, "csrf_token": session["csrf_token"]})




@bp.post("/signup")
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

@bp.post("/login")
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

@bp.post("/become-seller")
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

