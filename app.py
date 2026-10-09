"""WSGI entry point; business logic lives in the kidareh package."""
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
