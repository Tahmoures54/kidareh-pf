"""Health endpoint for the web service and its local storage dependencies."""
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from ..core import get_connection

bp = Blueprint("system", __name__)


@bp.get("/api/health")
def health():
    database_ok = False
    uploads_ok = False
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        database_ok = True
    except (sqlite3.Error, OSError):
        database_ok = False

    try:
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(parents=True, exist_ok=True)
        uploads_ok = upload_folder.is_dir() and os.access(upload_folder, os.W_OK)
    except OSError:
        uploads_ok = False

    ok = database_ok and uploads_ok
    return jsonify({
        "ok": ok,
        "service": "kidareh-pf",
        "database": "ok" if database_ok else "unavailable",
        "uploads": "writable" if uploads_ok else "unavailable",
    }), (200 if ok else 503)
