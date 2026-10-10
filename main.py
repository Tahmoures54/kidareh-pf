"""Application entry point for local runs, Gunicorn, and Liara."""
import os
from pathlib import Path

import kidareh.core as core
from kidareh import create_app

BASE_DIR = core.BASE_DIR
INSTANCE_DIR = core.INSTANCE_DIR
DATABASE_PATH = core.DATABASE_PATH
UPLOAD_FOLDER = core.UPLOAD_FOLDER
MAX_IMAGE_BYTES = core.MAX_IMAGE_BYTES
CATEGORIES = core.CATEGORIES
DEMO_LISTINGS = core.DEMO_LISTINGS

app = create_app()


def get_connection():
    core.DATABASE_PATH = Path(DATABASE_PATH)
    app.config["DATABASE_PATH"] = str(DATABASE_PATH)
    return core.get_connection()


def initialize_database():
    core.DATABASE_PATH = Path(DATABASE_PATH)
    app.config["DATABASE_PATH"] = str(DATABASE_PATH)
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
    return core.initialize_database()


initialize_database()


def main() -> None:
    """Run the production WSGI server when Liara invokes `python3 main.py`."""
    port = os.environ.get("PORT", "8000")
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "--bind",
            f"0.0.0.0:{port}",
            "--workers",
            os.environ.get("WEB_CONCURRENCY", "2"),
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
            "main:app",
        ],
    )


if __name__ == "__main__":
    main()
