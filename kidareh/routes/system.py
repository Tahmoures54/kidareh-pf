from flask import Blueprint, jsonify
bp = Blueprint("system", __name__)


@bp.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "kidareh-pf"})

