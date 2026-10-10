from __future__ import annotations
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from flask import current_app, has_app_context, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from .data_catalog import CATEGORIES, CATEGORY_LABELS

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

# --- Database path resolution -------------------------------------------------
# Priority:
#   1. DATABASE_PATH (explicit)
#   2. DB_PATH (legacy / Vercel dashboard name)
#   3. On Vercel: /tmp/instance/kidareh.sqlite3 (only writable location)
#   4. Local dev: <project>/instance/kidareh.sqlite3
def _resolve_database_path() -> Path:
    for key in ("DATABASE_PATH", "DB_PATH"):
        value = os.environ.get(key, "").strip()
        if value:
            return Path(value)
    if os.environ.get("VERCEL"):
        return Path("/tmp/instance/kidareh.sqlite3")
    return INSTANCE_DIR / "kidareh.sqlite3"


def _resolve_upload_folder() -> Path:
    value = os.environ.get("UPLOAD_FOLDER", "").strip()
    if value:
        return Path(value)
    if os.environ.get("VERCEL"):
        return Path("/tmp/uploads")
    return BASE_DIR / "static" / "uploads"


DATABASE_PATH = _resolve_database_path()
UPLOAD_FOLDER = _resolve_upload_folder()
MAX_IMAGE_BYTES = 4 * 1024 * 1024

# Category catalog is loaded from the versioned taxonomy in kidareh/data.


DEMO_LISTINGS = [
    ("گوشی سامسونگ تمیز و سالم", "digital", "تهران", 12800000, "گوشی سالم با حافظه مناسب؛ امکان بررسی حضوری.", "📱", 1),
    ("میز کار چوبی مینیمال", "home", "تبریز", 2450000, "میز مرتب و خوش‌ساخت، مناسب خانه و دفتر کار.", "🪑", 1),
    ("دوچرخه شهری کم‌کارکرد", "vehicle", "تهران", 5600000, "دوچرخه شهری آماده استفاده، بازدید با هماهنگی.", "🚲", 0),
    ("کتانی روزمره در حد نو", "fashion", "شیراز", 980000, "راحت و سبک، وضعیت بسیار خوب.", "👟", 0),
    ("تعمیر و سرویس لپ‌تاپ", "services", "اصفهان", 450000, "عیب‌یابی و سرویس با اعلام هزینه پیش از انجام کار.", "🧰", 1),
    ("چراغ مطالعه مدرن", "home", "رشت", 620000, "نور مناسب مطالعه با طراحی ساده و جمع‌وجور.", "💡", 0),
    ("هدفون بی‌سیم", "digital", "مشهد", 1750000, "هدفون روزمره با کیفیت صدای مناسب.", "🎧", 0),
    ("کوله‌پشتی روزانه", "fashion", "کرج", 890000, "جادار و مناسب دانشگاه و استفاده روزانه.", "🎒", 0),
]


def get_connection() -> sqlite3.Connection:
    database_path = Path(current_app.config.get("DATABASE_PATH", DATABASE_PATH)) if has_app_context() else DATABASE_PATH
    # Never silently switch databases: that can make production writes appear lost.
    # A configured path failure must be visible so the deployment can be fixed.
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute("PRAGMA cache_size = -65536")
    connection.execute("PRAGMA mmap_size = 268435456")
    return connection


def _ensure_performance_indexes(connection: sqlite3.Connection) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category)",
        "CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city)",
        "CREATE INDEX IF NOT EXISTS idx_listings_store_id ON listings(store_id)",
        "CREATE INDEX IF NOT EXISTS idx_listings_owner_id ON listings(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_listings_featured_id ON listings(featured DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_listings_geo ON listings(latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_stores_city ON stores(city)",
        "CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name)",
        "CREATE INDEX IF NOT EXISTS idx_listing_tags_listing_status ON listing_tags(listing_id, status, ends_at)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
    ]
    for sql in statements:
        connection.execute(sql)


def _ensure_listings_fts(connection: sqlite3.Connection) -> None:
    """Create FTS5 index for listings and keep it in sync via triggers.

    External-content FTS (`content='listings'`) reports COUNT(*) from the
    content table even when the inverted index is empty, so we cannot use
    COUNT as a signal to rebuild. Instead we inspect fts5vocab term count.
    """
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS listings_fts USING fts5(
            title,
            description,
            city,
            content='listings',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 0'
        )
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS listings_fts_ai AFTER INSERT ON listings BEGIN
            INSERT INTO listings_fts(rowid, title, description, city)
            VALUES (new.id, new.title, new.description, new.city);
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS listings_fts_ad AFTER DELETE ON listings BEGIN
            INSERT INTO listings_fts(listings_fts, rowid, title, description, city)
            VALUES ('delete', old.id, old.title, old.description, old.city);
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS listings_fts_au AFTER UPDATE OF title, description, city ON listings BEGIN
            INSERT INTO listings_fts(listings_fts, rowid, title, description, city)
            VALUES ('delete', old.id, old.title, old.description, old.city);
            INSERT INTO listings_fts(rowid, title, description, city)
            VALUES (new.id, new.title, new.description, new.city);
        END
        """
    )
    listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    if not listing_count:
        return
    # COUNT(*) on external-content FTS equals content rows even with an empty
    # inverted index — probe vocabulary instead.
    needs_rebuild = True
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS _listings_fts_vocab "
            "USING fts5vocab(listings_fts, 'row')"
        )
        term_count = connection.execute("SELECT COUNT(*) FROM _listings_fts_vocab").fetchone()[0]
        connection.execute("DROP TABLE IF EXISTS _listings_fts_vocab")
        needs_rebuild = term_count == 0
    except Exception:
        needs_rebuild = True
    if needs_rebuild:
        connection.execute("INSERT INTO listings_fts(listings_fts) VALUES('rebuild')")


def _should_seed_demo_data() -> bool:
    """Seed showcase records locally by default, but require explicit opt-in in production."""
    configured = os.environ.get("KIDAREH_SEED_DEMO_DATA")
    is_production = bool(
        os.environ.get("LIARA_APP_ID")
        or os.environ.get("FLASK_ENV", "").lower() == "production"
        or os.environ.get("ENV", "").lower() == "production"
    )
    if is_production:
        return (configured or "").strip().lower() in {"1", "true", "yes"}
    if configured is None:
        return True
    return configured.strip().lower() in {"1", "true", "yes"}


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                city TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL DEFAULT '',
                emoji TEXT NOT NULL DEFAULT '🛍️',
                featured INTEGER NOT NULL DEFAULT 0,
                image_path TEXT NOT NULL DEFAULT '',
                seller_phone TEXT NOT NULL DEFAULT '',
                owner_id INTEGER,
                store_id INTEGER,
                latitude REAL,
                longitude REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS listing_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tag_type TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                order_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_tags_order ON listing_tags(order_id)")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(listings)")}
        if "image_path" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")
        if "seller_phone" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN seller_phone TEXT NOT NULL DEFAULT ''")
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN owner_id INTEGER")
        if "store_id" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN store_id INTEGER")
        if "latitude" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN latitude REAL")
        if "longitude" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN longitude REAL")
        if "featured_until" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN featured_until TEXT NOT NULL DEFAULT ''")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'buyer',
                phone_verified_at TEXT NOT NULL DEFAULT '',
                terms_accepted_at TEXT NOT NULL DEFAULT '',
                is_banned INTEGER NOT NULL DEFAULT 0,
                ban_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "role" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'buyer'")
        if "phone_verified_at" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN phone_verified_at TEXT NOT NULL DEFAULT ''")
        if "terms_accepted_at" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN terms_accepted_at TEXT NOT NULL DEFAULT ''")
        if "is_banned" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
        if "ban_reason" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT NOT NULL DEFAULT ''")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                contact_name TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                hours TEXT NOT NULL DEFAULT '',
                social_url TEXT NOT NULL DEFAULT '',
                in_person INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            )
        """)
        store_columns = {row["name"] for row in connection.execute("PRAGMA table_info(stores)")}
        for column, declaration in ((
            "category", "TEXT NOT NULL DEFAULT ''"), ("contact_name", "TEXT NOT NULL DEFAULT ''"),
            ("address", "TEXT NOT NULL DEFAULT ''"), ("hours", "TEXT NOT NULL DEFAULT ''"),
            ("social_url", "TEXT NOT NULL DEFAULT ''"), ("in_person", "INTEGER NOT NULL DEFAULT 1"),
            ("latitude", "REAL"), ("longitude", "REAL"),
        ):
            if column not in store_columns:
                connection.execute(f"ALTER TABLE stores ADD COLUMN {column} {declaration}")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_stores_geo ON stores(latitude, longitude) "
            "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS store_follows (
                user_id INTEGER NOT NULL,
                store_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, store_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS saved_products (
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, listing_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE
            )
        """)
        if _should_seed_demo_data():
            store_count = connection.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
            if store_count == 0:
                connection.executemany(
                    "INSERT INTO stores (owner_id, name, city, description) VALUES (NULL, ?, ?, ?)",
                    [
                        ("خانه‌چین", "تهران", "لوازم کاربردی خانه و زندگی؛ بازدید و خرید حضوری"),
                        ("دیجیتال‌کده", "تبریز", "کالاهای دیجیتال و لوازم جانبی"),
                        ("بازار محلی", "شیراز", "کالاهای روزمره و انتخاب‌های محلی"),
                    ],
                )
            count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            if count == 0:
                connection.executemany(
                    """
                    INSERT INTO listings
                        (title, category, city, price, description, emoji, featured)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    DEMO_LISTINGS,
                )
            connection.execute("""
                UPDATE listings SET store_id = (
                    SELECT id FROM stores
                    WHERE stores.owner_id IS NULL
                      AND ((listings.category = 'home' AND stores.name = 'خانه‌چین')
                        OR (listings.category = 'digital' AND stores.name = 'دیجیتال‌کده')
                        OR (listings.category NOT IN ('home', 'digital') AND stores.name = 'بازار محلی'))
                    LIMIT 1
                )
                WHERE store_id IS NULL
            """)
        _ensure_performance_indexes(connection)
        _ensure_listings_fts(connection)


def serialize_listing(row: sqlite3.Row, include_contact: bool = False) -> dict[str, Any]:
    item = dict(row)
    item["featured"] = bool(item["featured"])
    item["category_name"] = CATEGORY_LABELS.get(item.get("category"), item.get("category", ""))
    item.pop("password_hash", None)
    if not include_contact:
        item.pop("seller_phone", None)
    item["can_edit"] = bool(session.get("user_id") and item.get("owner_id") == session.get("user_id"))
    return item


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_connection() as connection:
        row = connection.execute("SELECT id, name, phone, role, phone_verified_at, is_banned, ban_reason FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["is_banned"]:
        session.clear()
        return None
    return dict(row)


def csrf_valid():
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and __import__("hmac").compare_digest(expected, supplied))
