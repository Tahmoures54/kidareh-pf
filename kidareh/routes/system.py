"""Health endpoint for the web service and its database dependency."""
import sqlite3
from flask import Blueprint, jsonify
from ..core import get_connection
bp = Blueprint("system", __name__)

@bp.get("/api/health")
def health():
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
    except (sqlite3.Error, OSError):
        return jsonify({"ok": False, "service": "kidareh-pf", "database": "unavailable"}), 503
    return jsonify({"ok": True, "service": "kidareh-pf", "database": "ok"})
