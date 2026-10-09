import re
import sqlite3
import uuid
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from ..core import current_user, csrf_valid, get_connection

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


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

