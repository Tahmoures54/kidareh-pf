"""Application factory for the Kidareh marketplace."""
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from .core import BASE_DIR, CATEGORIES, DATABASE_PATH, MAX_IMAGE_BYTES, UPLOAD_FOLDER
from .data_catalog import CATEGORY_TREE, TRADE_GROUPS

_DEFAULT_SECRET = "dev-only-change-this-key"


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    secret_key = os.environ.get("SECRET_KEY", _DEFAULT_SECRET)
    is_production = (
        os.environ.get("FLASK_ENV", "").lower() == "production"
        or os.environ.get("ENV", "").lower() == "production"
        or os.environ.get("LIARA_APP_ID")  # Liara sets this in production
    )
    if test_config is None and is_production and secret_key == _DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY must be set to a strong random value in production. "
            "Do not use the development default."
        )
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES + 256 * 1024,
        DATABASE_PATH=str(DATABASE_PATH),
        UPLOAD_FOLDER=str(UPLOAD_FOLDER),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=bool(is_production),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    from .routes.pages import bp as pages_bp
    from .routes.auth import bp as auth_bp
    from .routes.stores import bp as stores_bp
    from .routes.listings import bp as listings_bp
    from .routes.system import bp as system_bp
    from .routes.monetization import bp as monetization_bp
    from .routes.moderation import bp as moderation_bp
    from .routes.communications import bp as communications_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(stores_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(monetization_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(communications_bp)

    @app.get("/sw.js")
    def service_worker():
        """Expose the service worker at the origin root so it can control the PWA."""
        response = send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
            max_age=0,
        )
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/static/uploads/<path:filename>")
    def uploaded_image(filename):
        """Serve only files from the configured uploads directory.

        This explicit route keeps the existing public URL stable while allowing
        UPLOAD_FOLDER to point at a persistent Liara disk mount.
        """
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        if Path(filename).suffix.lower() not in allowed_extensions:
            return jsonify({"error": "not_found"}), 404
        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            filename,
            conditional=True,
            max_age=86400,
        )

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "request_too_large", "message": "حجم درخواست بیش از حد مجاز است."}), 413

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found"}), 404
        from .core import CATEGORIES
        return render_template("index.html", categories=CATEGORIES, category_tree=CATEGORY_TREE, trade_groups=TRADE_GROUPS), 404

    return app
