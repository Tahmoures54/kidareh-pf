from flask import Blueprint, jsonify
bp = Blueprint("system", __name__)


def health():
    return jsonify({"ok": True, "service": "kidareh-pf"})

