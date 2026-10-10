"""Health endpoint for the web service and its local storage dependencies."""
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from ..core import get_connection

bp = Blueprint("system", __name__)

# A successful SQLite connection is not enough: an empty or incorrectly
# configured database can accept SELECT 1 while every business route fails.
_REQUIRED_TABLES = {"users", "stores", "listings"}


@bp.get("/api/health")
def health():
    database_status = "unavailable"
    uploads_ok = False
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
            existing_tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        missing_tables = _REQUIRED_TABLES - existing_tables
        database_status = "schema_incomplete" if missing_tables else "ok"
    except (sqlite3.Error, OSError):
        database_status = "unavailable"

    try:
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(parents=True, exist_ok=True)
        uploads_ok = upload_folder.is_dir() and os.access(upload_folder, os.W_OK)
    except OSError:
        uploads_ok = False

    ok = database_status == "ok" and uploads_ok
    return jsonify({
        "ok": ok,
        "service": "kidareh-pf",
        "database": database_status,
        "uploads": "writable" if uploads_ok else "unavailable",
    }), (200 if ok else 503)
