"""Authenticated content reports and a minimal phone-configured moderation queue."""
import os
from flask import Blueprint, jsonify, request
from ..core import current_user, csrf_valid, delete_uploaded_image, get_connection
from ..services import rate_limits

bp = Blueprint("moderation", __name__)

REPORT_REASONS = {"spam", "fraud", "wrong_info", "prohibited", "other"}
REPORT_STATUSES = {"open", "resolved"}


def ensure_tables() -> None:
    """Create the report queue during start-up so requests never run DDL."""
    with get_connection() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS content_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                target_type TEXT NOT NULL CHECK(target_type IN ('listing','store')),
                target_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT NOT NULL DEFAULT ''
            )"""
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_reports_status ON content_reports(status,id DESC)"
        )


def is_admin(user):
    phone = os.environ.get("ADMIN_PHONE", "").strip()
    return bool(user and phone and user.get("phone") == phone and user.get("phone_verified_at"))


def _require_admin():
    """Return an error response when the caller is not the configured admin."""
    user = current_user()
    if not is_admin(user):
        return jsonify({"error": "admin_required", "message": "دسترسی مدیر لازم است."}), 403
    return None


@bp.post("/api/reports")
def create_report():
    user = current_user()
    if not user:
        return jsonify({"error": "authentication_required", "message": "برای ثبت گزارش وارد حساب شوید."}), 401
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400

    payload = request.get_json(silent=True) or {}
    kind = payload.get("target_type")
    target = payload.get("target_id")
    reason = payload.get("reason")
    details = payload.get("details", "")

    if kind not in {"listing", "store"} or not isinstance(target, int) or isinstance(target, bool) or target < 1:
        return jsonify({"error": "invalid_target"}), 400
    if reason not in REPORT_REASONS or not isinstance(details, str) or len(details) > 500:
        return jsonify({"error": "invalid_report"}), 400

    try:
        rate_limits.enforce("report_create", user, limit=10, window_seconds=3600)
    except rate_limits.RateLimitExceeded as error:
        return rate_limits.error_response(error, "تعداد گزارش‌های شما از سقف ساعتی گذشته است.")

    with get_connection() as db:
        table = "listings" if kind == "listing" else "stores"
        if not db.execute(f"SELECT id FROM {table} WHERE id=?", (target,)).fetchone():
            return jsonify({"error": "target_not_found"}), 404
        db.execute(
            "INSERT INTO content_reports(reporter_id,target_type,target_id,reason,details) VALUES(?,?,?,?,?)",
            (user["id"], kind, target, reason, details.strip()),
        )
    return jsonify({"ok": True, "message": "گزارش شما ثبت شد."}), 201


@bp.get("/api/admin/reports")
def list_reports():
    error = _require_admin()
    if error:
        return error

    status = request.args.get("status", "open")
    if status not in {"open", "resolved", "all"}:
        return jsonify({"error": "invalid_status"}), 400

    sql = "SELECT r.*,u.name AS reporter_name FROM content_reports r JOIN users u ON u.id=r.reporter_id"
    parameters = ()
    if status != "all":
        sql += " WHERE r.status=?"
        parameters = (status,)
    sql += " ORDER BY r.id DESC LIMIT 200"

    with get_connection() as db:
        rows = db.execute(sql, parameters).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.patch("/api/admin/reports/<int:report_id>")
def review_report(report_id):
    error = _require_admin()
    if error:
        return error
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400

    payload = request.get_json(silent=True) or {}
    if payload.get("status") not in REPORT_STATUSES:
        return jsonify({"error": "invalid_status"}), 400

    image_path = ""
    with get_connection() as db:
        report = db.execute("SELECT * FROM content_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            return jsonify({"error": "report_not_found"}), 404
        db.execute(
            "UPDATE content_reports SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
            (payload["status"], report_id),
        )
        if payload.get("hide_target") is True and report["target_type"] == "listing":
            listing = db.execute(
                "SELECT image_path FROM listings WHERE id=?", (report["target_id"],)
            ).fetchone()
            if listing and listing["image_path"]:
                image_path = listing["image_path"]
            db.execute("DELETE FROM listings WHERE id=?", (report["target_id"],))
    if image_path:
        delete_uploaded_image(image_path)
    return jsonify({"ok": True})
