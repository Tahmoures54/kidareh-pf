"""Authenticated content reports and a minimal phone-configured moderation queue."""
import os
import uuid
from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template, request, session
from ..core import current_user, csrf_valid, get_connection
bp = Blueprint("moderation", __name__)

def ensure_table():
    with get_connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS content_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, target_type TEXT NOT NULL CHECK(target_type IN ('listing','store')), target_id INTEGER NOT NULL, reason TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT NOT NULL DEFAULT '')""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_content_reports_status ON content_reports(status,id DESC)")
def is_admin(user):
    phone=os.environ.get("ADMIN_PHONE","").strip()
    return bool(user and phone and user.get("phone")==phone and user.get("phone_verified_at"))

def _delete_listing_image(image_path: str) -> None:
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

@bp.post("/api/reports")
def create_report():
    user=current_user()
    if not user:return jsonify({"error":"authentication_required","message":"برای ثبت گزارش وارد حساب شوید."}),401
    if not csrf_valid():return jsonify({"error":"csrf_failed"}),400
    p=request.get_json(silent=True) or {};kind=p.get("target_type");target=p.get("target_id");reason=p.get("reason");details=p.get("details","")
    if kind not in {"listing","store"} or not isinstance(target,int) or target<1:return jsonify({"error":"invalid_target"}),400
    if reason not in {"spam","fraud","wrong_info","prohibited","other"} or not isinstance(details,str) or len(details)>500:return jsonify({"error":"invalid_report"}),400
    ensure_table()
    with get_connection() as db:
        table="listings" if kind=="listing" else "stores"
        if not db.execute(f"SELECT id FROM {table} WHERE id=?",(target,)).fetchone():return jsonify({"error":"target_not_found"}),404
        recent=db.execute("SELECT COUNT(*) FROM content_reports WHERE reporter_id=? AND created_at>=datetime('now','-1 hour')",(user["id"],)).fetchone()[0]
        if recent>=10:return jsonify({"error":"report_limit"}),429
        db.execute("INSERT INTO content_reports(reporter_id,target_type,target_id,reason,details) VALUES(?,?,?,?,?)",(user["id"],kind,target,reason,details.strip()))
    return jsonify({"ok":True,"message":"گزارش شما ثبت شد."}),201
@bp.get("/api/admin/reports")
def list_reports():
    user=current_user()
    if not is_admin(user):return jsonify({"error":"admin_required"}),403
    ensure_table();status=request.args.get("status","open")
    if status not in {"open","resolved","all"}:return jsonify({"error":"invalid_status"}),400
    sql="SELECT r.*,u.name AS reporter_name FROM content_reports r JOIN users u ON u.id=r.reporter_id"
    if status!="all":sql+=" WHERE r.status=?"
    sql+=" ORDER BY r.id DESC LIMIT 200"
    with get_connection() as db:rows=db.execute(sql,(status,) if status!="all" else ()).fetchall()
    return jsonify({"items":[dict(row) for row in rows]})
@bp.patch("/api/admin/reports/<int:report_id>")
def review_report(report_id):
    user=current_user()
    if not is_admin(user):return jsonify({"error":"admin_required"}),403
    if not csrf_valid():return jsonify({"error":"csrf_failed"}),400
    p=request.get_json(silent=True) or {}
    if p.get("status") not in {"open","resolved"}:return jsonify({"error":"invalid_status"}),400
    ensure_table()
    image_path = ""
    with get_connection() as db:
        report=db.execute("SELECT * FROM content_reports WHERE id=?",(report_id,)).fetchone()
        if not report:return jsonify({"error":"report_not_found"}),404
        db.execute("UPDATE content_reports SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(p["status"],report_id))
        if p.get("hide_target") is True and report["target_type"]=="listing":
            listing = db.execute("SELECT image_path FROM listings WHERE id=?", (report["target_id"],)).fetchone()
            if listing and listing["image_path"]:
                image_path = listing["image_path"]
            db.execute("DELETE FROM listings WHERE id=?",(report["target_id"],))
    if image_path:
        _delete_listing_image(image_path)
    return jsonify({"ok":True})
@bp.get("/admin/reports")
def reports_page():
    if not session.get("csrf_token"):session["csrf_token"]=uuid.uuid4().hex
    return render_template("pages/admin/reports.html",csrf_token=session["csrf_token"])
