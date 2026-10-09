"""Application factory for the Kidareh marketplace."""
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .core import BASE_DIR, DATABASE_PATH, MAX_IMAGE_BYTES, UPLOAD_FOLDER

def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-key"),
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES + 256 * 1024,
        DATABASE_PATH=str(DATABASE_PATH),
        UPLOAD_FOLDER=str(UPLOAD_FOLDER),
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

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "request_too_large", "message": "حجم درخواست بیش از حد مجاز است."}), 413

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found"}), 404
        from .core import CATEGORIES
        return render_template("index.html", categories=CATEGORIES), 404

    return app
