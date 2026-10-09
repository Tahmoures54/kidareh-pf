"""Buyer/seller conversations, customer support tickets, and admin overview."""
import os
from flask import Blueprint, jsonify, render_template, request, session
from ..core import current_user, csrf_valid, get_connection

bp = Blueprint("communications", __name__)


def is_admin(user):
    admin_phone = os.environ.get("ADMIN_PHONE", "").strip()
    return bool(user and admin_phone and user.get("phone") == admin_phone and user.get("phone_verified_at"))


def require_user():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "authentication_required", "message": "برای ادامه وارد حساب شوید."}), 401)
    return user, None


def ensure_tables():
    with get_connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(listing_id, buyer_id),
            CHECK(buyer_id <> seller_id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_buyer ON conversations(buyer_id, updated_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_seller ON conversations(seller_id, updated_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            read_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread ON conversation_messages(conversation_id, id)")
        db.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','answered','closed')),
            priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('low','normal','high')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            is_admin_reply INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, updated_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id, id)")


def ensure_admin_schema(db):
    cols = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "is_banned" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
    if "ban_reason" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT NOT NULL DEFAULT ''")


@bp.get("/api/conversations")
def list_conversations():
    user, error = require_user()
    if error:
        return error
    ensure_tables()
    with get_connection() as db:
        rows = db.execute("""
            SELECT c.id, c.listing_id, l.title AS listing_title,
                   CASE WHEN c.buyer_id=? THEN seller.name ELSE buyer.name END AS other_name,
                   CASE WHEN c.buyer_id=? THEN seller.id ELSE buyer.id END AS other_user_id,
                   c.updated_at,
                   (SELECT body FROM conversation_messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                   (SELECT COUNT(*) FROM conversation_messages m WHERE m.conversation_id=c.id AND m.sender_id<>? AND m.read_at='') AS unread_count
            FROM conversations c
            JOIN users buyer ON buyer.id=c.buyer_id
            JOIN users seller ON seller.id=c.seller_id
            JOIN listings l ON l.id=c.listing_id
            WHERE c.buyer_id=? OR c.seller_id=?
            ORDER BY c.updated_at DESC
        """, (user["id"], user["id"], user["id"], user["id"], user["id"])).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.post("/api/conversations")
def start_conversation():
    user, error = require_user()
    if error:
        return error
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    listing_id = payload.get("listing_id")
    if not isinstance(listing_id, int) or listing_id < 1:
        return jsonify({"error": "invalid_listing"}), 400
    ensure_tables()
    with get_connection() as db:
        listing = db.execute("SELECT id, title, owner_id, store_id FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not listing:
            return jsonify({"error": "listing_not_found"}), 404
        seller_id = listing["owner_id"]
        if not seller_id and listing["store_id"]:
            store = db.execute("SELECT owner_id FROM stores WHERE id=?", (listing["store_id"],)).fetchone()
            seller_id = store["owner_id"] if store else None
        if not seller_id:
            return jsonify({"error": "seller_unavailable", "message": "برای این کالای قدیمی هنوز حساب فروشنده متصل نیست."}), 409
        if seller_id == user["id"]:
            return jsonify({"error": "own_listing", "message": "برای کالای خودتان نمی‌توانید گفت‌وگو شروع کنید."}), 400
        db.execute("INSERT OR IGNORE INTO conversations(listing_id,buyer_id,seller_id) VALUES(?,?,?)", (listing_id, user["id"], seller_id))
        thread = db.execute("SELECT id FROM conversations WHERE listing_id=? AND buyer_id=?", (listing_id, user["id"])).fetchone()
    return jsonify({"id": thread["id"], "listing_title": listing["title"]}), 201


@bp.get("/api/conversations/<int:conversation_id>/messages")
def conversation_messages(conversation_id):
    user, error = require_user()
    if error:
        return error
    ensure_tables()
    with get_connection() as db:
        thread = db.execute("SELECT * FROM conversations WHERE id=? AND (buyer_id=? OR seller_id=?)", (conversation_id, user["id"], user["id"])).fetchone()
        if not thread:
            return jsonify({"error": "conversation_not_found"}), 404
        db.execute("UPDATE conversation_messages SET read_at=CURRENT_TIMESTAMP WHERE conversation_id=? AND sender_id<>? AND read_at=''", (conversation_id, user["id"]))
        rows = db.execute("SELECT m.id,m.sender_id,m.body,m.created_at,m.read_at,u.name AS sender_name FROM conversation_messages m JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? ORDER BY m.id ASC LIMIT 500", (conversation_id,)).fetchall()
        listing = db.execute("SELECT title FROM listings WHERE id=?", (thread["listing_id"],)).fetchone()
    return jsonify({"conversation": {"id": conversation_id, "listing_title": listing["title"] if listing else "کالای حذف‌شده"}, "items": [dict(row) for row in rows]})


@bp.post("/api/conversations/<int:conversation_id>/messages")
def send_conversation_message(conversation_id):
    user, error = require_user()
    if error:
        return error
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    body = payload.get("body")
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > 2000:
        return jsonify({"error": "invalid_message", "message": "پیام باید بین ۱ تا ۲۰۰۰ نویسه باشد."}), 400
    ensure_tables()
    with get_connection() as db:
        thread = db.execute("SELECT * FROM conversations WHERE id=? AND (buyer_id=? OR seller_id=?)", (conversation_id, user["id"], user["id"])).fetchone()
        if not thread:
            return jsonify({"error": "conversation_not_found"}), 404
        cursor = db.execute("INSERT INTO conversation_messages(conversation_id,sender_id,body) VALUES(?,?,?)", (conversation_id, user["id"], body.strip()))
        db.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))
        row = db.execute("SELECT id,sender_id,body,created_at,read_at FROM conversation_messages WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify({"item": dict(row)}), 201


@bp.get("/api/support/tickets")
def support_list():
    user, error = require_user()
    if error:
        return error
    ensure_tables()
    with get_connection() as db:
        rows = db.execute("""SELECT t.*,
          (SELECT body FROM support_messages m WHERE m.ticket_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_message,
          (SELECT COUNT(*) FROM support_messages m WHERE m.ticket_id=t.id AND m.is_admin_reply=1 AND m.id>(SELECT COALESCE(MAX(own.id),0) FROM support_messages own WHERE own.ticket_id=t.id AND own.sender_id=?)) AS new_replies
          FROM support_tickets t WHERE t.user_id=? ORDER BY t.updated_at DESC""", (user["id"], user["id"])).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.post("/api/support/tickets")
def support_create():
    user, error = require_user()
    if error:
        return error
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    title, body = payload.get("title"), payload.get("body")
    category = payload.get("category", "general")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 120:
        return jsonify({"error": "invalid_title", "message": "موضوع باید بین ۳ تا ۱۲۰ نویسه باشد."}), 400
    if not isinstance(body, str) or not 10 <= len(body.strip()) <= 4000:
        return jsonify({"error": "invalid_message", "message": "شرح درخواست باید بین ۱۰ تا ۴۰۰۰ نویسه باشد."}), 400
    if category not in {"general", "account", "listing", "payment", "technical", "other"}:
        return jsonify({"error": "invalid_category"}), 400
    ensure_tables()
    with get_connection() as db:
        recent = db.execute("SELECT COUNT(*) FROM support_tickets WHERE user_id=? AND created_at>=datetime('now','-1 day')", (user["id"],)).fetchone()[0]
        if recent >= 10:
            return jsonify({"error": "ticket_limit", "message": "سقف ثبت تیکت روزانه پر شده است."}), 429
        cursor = db.execute("INSERT INTO support_tickets(user_id,title,category) VALUES(?,?,?)", (user["id"], title.strip(), category))
        db.execute("INSERT INTO support_messages(ticket_id,sender_id,body,is_admin_reply) VALUES(?,?,?,0)", (cursor.lastrowid, user["id"], body.strip()))
    return jsonify({"ok": True, "id": cursor.lastrowid}), 201


@bp.get("/api/support/tickets/<int:ticket_id>")
def support_detail(ticket_id):
    user, error = require_user()
    if error:
        return error
    ensure_tables()
    with get_connection() as db:
        ticket = db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket:
            return jsonify({"error": "ticket_not_found"}), 404
        if ticket["user_id"] != user["id"] and not is_admin(user):
            return jsonify({"error": "ticket_forbidden"}), 403
        messages = db.execute("SELECT m.id,m.sender_id,m.body,m.is_admin_reply,m.created_at,u.name AS sender_name FROM support_messages m JOIN users u ON u.id=m.sender_id WHERE m.ticket_id=? ORDER BY m.id ASC", (ticket_id,)).fetchall()
    return jsonify({"ticket": dict(ticket), "items": [dict(row) for row in messages]})


@bp.post("/api/support/tickets/<int:ticket_id>/messages")
def support_reply(ticket_id):
    user, error = require_user()
    if error:
        return error
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    body = payload.get("body")
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 4000:
        return jsonify({"error": "invalid_message", "message": "پاسخ باید حداکثر ۴۰۰۰ نویسه باشد."}), 400
    ensure_tables()
    with get_connection() as db:
        ticket = db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket:
            return jsonify({"error": "ticket_not_found"}), 404
        admin = is_admin(user)
        if ticket["user_id"] != user["id"] and not admin:
            return jsonify({"error": "ticket_forbidden"}), 403
        if ticket["status"] == "closed":
            return jsonify({"error": "ticket_closed", "message": "این تیکت بسته شده است."}), 409
        db.execute("INSERT INTO support_messages(ticket_id,sender_id,body,is_admin_reply) VALUES(?,?,?,?)", (ticket_id, user["id"], body.strip(), int(admin)))
        new_status = "answered" if admin else "open"
        db.execute("UPDATE support_tickets SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, ticket_id))
    return jsonify({"ok": True}), 201


@bp.get("/api/admin/dashboard")
def admin_dashboard():
    user, error = require_user()
    if error:
        return error
    if not is_admin(user):
        return jsonify({"error": "admin_required"}), 403
    ensure_tables()
    with get_connection() as db:
        ensure_admin_schema(db)
        counts = {
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "buyers": db.execute("SELECT COUNT(*) FROM users WHERE role='buyer'").fetchone()[0],
            "sellers": db.execute("SELECT COUNT(*) FROM users WHERE role='seller'").fetchone()[0],
            "banned": db.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0],
            "listings": db.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
            "stores": db.execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "open_tickets": db.execute("SELECT COUNT(*) FROM support_tickets WHERE status IN ('open','in_progress')").fetchone()[0],
            "open_reports": db.execute("SELECT COUNT(*) FROM content_reports WHERE status='open'").fetchone()[0] if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_reports'").fetchone() else 0,
        }
        order_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='monetization_orders'").fetchone()
        revenue = db.execute("SELECT COALESCE(SUM(amount_toman),0) FROM monetization_orders WHERE status IN ('paid','success','completed')").fetchone()[0] if order_table else 0
        users = db.execute("SELECT id,name,phone,role,is_banned,created_at FROM users ORDER BY id DESC LIMIT 100").fetchall()
        activity = db.execute("""SELECT 'listing' AS type, title AS label, created_at FROM listings
             UNION ALL SELECT 'user' AS type, name AS label, created_at FROM users
             UNION ALL SELECT 'ticket' AS type, title AS label, created_at FROM support_tickets
             ORDER BY created_at DESC LIMIT 12""").fetchall()
        tickets = db.execute("""SELECT t.id,t.title,t.status,t.priority,t.updated_at,u.name AS user_name,u.phone
            FROM support_tickets t JOIN users u ON u.id=t.user_id
            ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, t.updated_at DESC LIMIT 50""").fetchall()
    return jsonify({"counts": counts, "revenue_toman": int(revenue or 0), "users": [dict(row) for row in users], "activity": [dict(row) for row in activity], "tickets": [dict(row) for row in tickets]})


@bp.patch("/api/admin/users/<int:user_id>")
def admin_update_user(user_id):
    user, error = require_user()
    if error:
        return error
    if not is_admin(user):
        return jsonify({"error": "admin_required"}), 403
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    if "is_banned" not in payload or not isinstance(payload["is_banned"], bool):
        return jsonify({"error": "invalid_user_update"}), 400
    ensure_tables()
    with get_connection() as db:
        ensure_admin_schema(db)
        target = db.execute("SELECT id,phone FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            return jsonify({"error": "user_not_found"}), 404
        if target["id"] == user["id"] or target["phone"] == os.environ.get("ADMIN_PHONE", "").strip():
            return jsonify({"error": "protected_user", "message": "حساب مدیر اصلی قابل مسدودسازی نیست."}), 400
        db.execute("UPDATE users SET is_banned=?,ban_reason=? WHERE id=?", (int(payload["is_banned"]), str(payload.get("reason", ""))[:300] if payload["is_banned"] else "", user_id))
    return jsonify({"ok": True})


@bp.patch("/api/admin/tickets/<int:ticket_id>")
def admin_update_ticket(ticket_id):
    user, error = require_user()
    if error:
        return error
    if not is_admin(user):
        return jsonify({"error": "admin_required"}), 403
    if not csrf_valid():
        return jsonify({"error": "csrf_failed"}), 400
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in {"open", "in_progress", "answered", "closed"}:
        return jsonify({"error": "invalid_status"}), 400
    ensure_tables()
    with get_connection() as db:
        if not db.execute("SELECT id FROM support_tickets WHERE id=?", (ticket_id,)).fetchone():
            return jsonify({"error": "ticket_not_found"}), 404
        db.execute("UPDATE support_tickets SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, ticket_id))
    return jsonify({"ok": True})


@bp.get("/messages")
def messages_page():
    if not session.get("csrf_token"):
        import uuid
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("pages/account/messages.html", csrf_token=session["csrf_token"])


@bp.get("/support")
def support_page():
    if not session.get("csrf_token"):
        import uuid
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("pages/account/support.html", csrf_token=session["csrf_token"])


@bp.get("/admin")
def admin_page():
    if not session.get("csrf_token"):
        import uuid
        session["csrf_token"] = uuid.uuid4().hex
    return render_template("pages/admin/dashboard.html", csrf_token=session["csrf_token"])
