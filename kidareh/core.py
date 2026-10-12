from __future__ import annotations
import contextlib
import hmac
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterator
from flask import current_app, g, has_app_context, has_request_context, request, session
# CATEGORIES is re-exported: `main.py` and templates read it from this module.
from .data_catalog import CATEGORIES, CATEGORY_LABELS  # noqa: F401

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


def _configured_database_path() -> Path:
    """Resolve the active database path from the app config or module defaults."""
    if has_app_context():
        return Path(current_app.config.get("DATABASE_PATH", DATABASE_PATH))
    return Path(DATABASE_PATH)


# The connection bound to the current request, so a request that touches the
# database several times pays the connection set-up cost only once.
REQUEST_CONNECTION_KEY = "_kidareh_database_connection"

UPLOAD_URL_PREFIX = "/static/uploads/"


def _open_connection(database_path: Path) -> sqlite3.Connection:
    """Open and configure one SQLite connection."""
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


@contextlib.contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection and commit it on a clean exit.

    Inside a request the same connection is reused for every block and closed by
    the app-context teardown, which removes ~0.5 ms of connection set-up per
    block. Outside a request (start-up, scripts, tests) the connection is opened
    and closed by this context manager.

    Work is committed at the end of **each** block on purpose: SQLite allows a
    single writer, so a request-scoped transaction held across, say, a payment
    gateway call would block every other writer for the duration.
    """
    database_path = _configured_database_path()
    request_scoped = has_request_context()
    if request_scoped:
        connection = g.get(REQUEST_CONNECTION_KEY)
        if connection is None:
            connection = _open_connection(database_path)
            setattr(g, REQUEST_CONNECTION_KEY, connection)
    else:
        connection = _open_connection(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            connection.rollback()
        raise
    finally:
        if not request_scoped:
            connection.close()


def close_request_connection(_error=None) -> None:
    """Close the request-scoped connection, if one was opened."""
    connection = g.pop(REQUEST_CONNECTION_KEY, None)
    if connection is not None:
        with contextlib.suppress(sqlite3.Error):
            connection.close()


def upload_relative_path(filename: str) -> str:
    """Return the on-disk relative path for an uploaded file.

    Files are sharded into two-character directories: a directory with millions
    of entries in one flat folder slows every lookup down, while ``ab/abcd….jpg``
    keeps each directory to a few thousand entries.
    """
    return f"{filename[:2]}/{filename}"


def delete_uploaded_image(image_path: str) -> None:
    """Remove an uploaded image from disk if it lives under the uploads folder.

    Both sharded (``ab/name.jpg``) and legacy flat (``name.jpg``) paths are
    supported; path traversal is rejected before anything is unlinked.
    """
    if not isinstance(image_path, str) or not image_path.startswith(UPLOAD_URL_PREFIX):
        return
    parts = [part for part in image_path[len(UPLOAD_URL_PREFIX):].split("/") if part]
    if not parts or len(parts) > 2:
        return
    if any(part in (".", "..") or "\\" in part for part in parts):
        return
    target = Path(_configured_upload_folder()).joinpath(*parts)
    try:
        if target.is_file():
            target.unlink()
    except OSError:
        pass


def _configured_upload_folder() -> Path:
    if has_app_context():
        return Path(current_app.config.get("UPLOAD_FOLDER", UPLOAD_FOLDER))
    return Path(UPLOAD_FOLDER)


# Index name -> exact CREATE statement. Comparing definitions (not just names)
# is what makes this self-healing: `CREATE INDEX IF NOT EXISTS` silently does
# nothing when a name exists with a *different* definition, which is exactly how
# an upgraded deployment would keep a stale, narrower index forever.
PERFORMANCE_INDEXES: dict[str, str] = {
    "idx_listings_category_featured_id":
        "CREATE INDEX idx_listings_category_featured_id ON listings(category, featured DESC, id DESC)",
    "idx_listings_city_featured_id":
        "CREATE INDEX idx_listings_city_featured_id ON listings(city, featured DESC, id DESC)",
    "idx_listings_city_category_featured_id":
        "CREATE INDEX idx_listings_city_category_featured_id"
        " ON listings(city, category, featured DESC, id DESC)",
    "idx_listings_store_id":
        "CREATE INDEX idx_listings_store_id ON listings(store_id, id DESC)",
    "idx_listings_owner_id":
        "CREATE INDEX idx_listings_owner_id ON listings(owner_id, id DESC)",
    "idx_listings_featured_id":
        "CREATE INDEX idx_listings_featured_id ON listings(featured DESC, id DESC)",
    # Partial: only paid listings carry featured_until, so it stays tiny and lets
    # the expiry sweep jump straight to the rows that can expire.
    "idx_listings_featured_expiry":
        "CREATE INDEX idx_listings_featured_expiry ON listings(featured_until)"
        " WHERE featured_until <> ''",
    "idx_listings_geo":
        "CREATE INDEX idx_listings_geo ON listings(latitude, longitude)"
        " WHERE latitude IS NOT NULL AND longitude IS NOT NULL",
    "idx_stores_city_id":
        "CREATE INDEX idx_stores_city_id ON stores(city, id DESC)",
    "idx_stores_name":
        "CREATE INDEX idx_stores_name ON stores(name)",
    "idx_listing_tags_listing_status":
        "CREATE INDEX idx_listing_tags_listing_status ON listing_tags(listing_id, status, ends_at)",
    "idx_users_role":
        "CREATE INDEX idx_users_role ON users(role)",
    # Per-store counters are read on every store page; without an index whose
    # first column is store_id a follow count has to scan the whole table.
    "idx_store_follows_store":
        "CREATE INDEX idx_store_follows_store ON store_follows(store_id, user_id)",
    "idx_saved_products_user":
        "CREATE INDEX idx_saved_products_user ON saved_products(user_id, created_at DESC)",
    "idx_monetization_orders_user":
        "CREATE INDEX idx_monetization_orders_user ON monetization_orders(user_id, id DESC)",
    "idx_support_tickets_user":
        "CREATE INDEX idx_support_tickets_user ON support_tickets(user_id, id DESC)",
}

# Names the codebase no longer uses. Dropped so the writer does not keep
# maintaining an index no query can benefit from.
SUPERSEDED_INDEXES = (
    "idx_listings_category",
    "idx_listings_city",
    "idx_listings_category_id",
    "idx_listings_city_id",
)


def _normalize_index_sql(sql: str) -> str:
    """Comparable form of an index definition: no `IF NOT EXISTS`, single spaces."""
    return " ".join(sql.replace("IF NOT EXISTS", "").split())


def _ensure_performance_indexes(connection: sqlite3.Connection) -> None:
    """Create the indexes the read paths rely on, and repair changed ones.

    Browse queries are always "... ORDER BY featured DESC, id DESC LIMIT n".
    The indexes therefore carry the *sort columns in sort order* after the
    filter columns, which is what lets SQLite stream the first page straight out
    of the index and stop. Measured on 1,000,000 listings: a category filter
    that lacks `featured` in the index needs 257 ms (it must read every matching
    row to learn whether it is featured before it can sort); with it, the same
    query costs 0.15 ms.
    """
    for name in SUPERSEDED_INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {name}")

    existing = {
        row["name"]: _normalize_index_sql(row["sql"])
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        )
    }
    for name, statement in PERFORMANCE_INDEXES.items():
        if existing.get(name) == _normalize_index_sql(statement):
            continue
        if name in existing:
            # Same name, different definition: replace it.
            connection.execute(f"DROP INDEX IF EXISTS {name}")
        connection.execute(statement)


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
        # LIMIT 1 keeps this O(1): counting every distinct term would scan
        # millions of rows on every start-up for the same yes/no answer.
        has_terms = connection.execute(
            "SELECT 1 FROM _listings_fts_vocab LIMIT 1"
        ).fetchone()
        connection.execute("DROP TABLE IF EXISTS _listings_fts_vocab")
        needs_rebuild = has_terms is None
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


def _initialize_schema_v1() -> None:
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
                availability_status TEXT NOT NULL DEFAULT 'ask',
                price_updated_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # listing_tags is owned by the monetization module (it is created by
        # initialize_feature_schemas on every startup) and is deliberately not
        # defined here: one owner, one definition.
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
        if "availability_status" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN availability_status TEXT NOT NULL DEFAULT 'ask'")
        if "price_updated_at" not in columns:
            connection.execute("ALTER TABLE listings ADD COLUMN price_updated_at TEXT NOT NULL DEFAULT ''")
        connection.execute("UPDATE listings SET price_updated_at = created_at WHERE price_updated_at = ''")
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
                city TEXT NOT NULL DEFAULT '',
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
        if "city" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN city TEXT NOT NULL DEFAULT ''")
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
        # FTS and the performance indexes are ensured on every start-up (see
        # initialize_database) so an existing database also gains them.


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
        row = connection.execute("SELECT id, name, phone, role, city, phone_verified_at, is_banned, ban_reason FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["is_banned"]:
        session.clear()
        return None
    return dict(row)


def csrf_valid():
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


# Incremental, recoverable schema migrations. Version 1 adopts the existing
# idempotent initializers as the baseline for both fresh and legacy databases.
SCHEMA_VERSION = 1
SCHEMA_MIGRATIONS = ((1, _initialize_schema_v1),)

# Concurrent workers share one SQLite file, so schema work is serialized with a
# dedicated lock database that lives beside the real database file.
MIGRATION_LOCK_FILENAME = "kidareh-migrations.lock"
MIGRATION_LOCK_TIMEOUT_SECONDS = 120


@contextlib.contextmanager
def _schema_migration_lock(database_path: Path) -> Iterator[None]:
    """Serialize schema initialization across processes and workers.

    Gunicorn boots several workers at once and every worker runs
    ``initialize_database()`` while importing the application. Without a lock
    they all migrate, then collide on the primary key of ``schema_migrations``
    and one worker dies during deployment. The lock is a separate SQLite file so
    holding it never blocks the migrations themselves, and SQLite releases it
    automatically if a worker is killed mid-migration, so there is no stale
    lock left behind to clean up.
    """
    lock_path = database_path.parent / MIGRATION_LOCK_FILENAME
    connection = sqlite3.connect(
        lock_path, timeout=MIGRATION_LOCK_TIMEOUT_SECONDS, isolation_level=None
    )
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS migration_lock (id INTEGER PRIMARY KEY CHECK (id = 1))"
        )
        connection.execute("INSERT OR IGNORE INTO migration_lock (id) VALUES (1)")
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        finally:
            with contextlib.suppress(sqlite3.Error):
                connection.execute("ROLLBACK")
    finally:
        connection.close()


def initialize_database() -> None:
    """Apply each schema migration once and record it only after success.

    The migration ledger is intentionally separate from feature tables so a
    failed initialization is retried on the next startup instead of being
    marked as complete. Existing databases are safely adopted by migration 1.
    """
    # Import lazily: the feature modules import this module at start-up time.
    from .schema_init import initialize_feature_schemas

    database_path = _configured_database_path()
    # Never silently switch databases: a configured path failure must be visible
    # so the deployment can be fixed instead of losing production writes.
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with _schema_migration_lock(database_path):
        with get_connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            applied = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()[0]

        if applied > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {applied} is newer than this application supports "
                f"(maximum {SCHEMA_VERSION})."
            )

        for version, migration in SCHEMA_MIGRATIONS:
            if version <= applied:
                continue
            migration()
            with get_connection() as connection:
                connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
                )

        # Feature-owned tables are refreshed on every startup rather than only
        # inside a numbered migration, so databases that are already at the
        # latest version still gain tables added by feature modules later on.
        initialize_feature_schemas()

        # Both are idempotent and checked on every start-up, so a running
        # deployment gains new indexes or a missing FTS index without needing a
        # numbered migration.
        with get_connection() as connection:
            _ensure_listings_fts(connection)
            _ensure_performance_indexes(connection)
