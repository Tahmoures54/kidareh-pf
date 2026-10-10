"""Probe hot read paths against a seeded SQLite database.

Usage:
    python scripts/scale_profiles.py [--listings 1000000] [--stores 100000]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import tempfile
import time
from pathlib import Path

from kidareh import create_app
from kidareh.core import get_connection, initialize_database

CITIES = ["تهران", "مشهد", "اصفهان", "کرج", "شیراز", "تبریز", "قم", "اهواز", "یزد", "رشت"]
CATEGORIES = ["home", "digital", "fashion", "vehicle", "services", "other"]
TITLE_WORDS = ["دوچرخه", "کوهستان", "حرفه‌ای", "مدل", "جدید", "آکبند", "تعمیرکار", "برقی"]
SEARCHES = ["دوچرخه"]


def build(app, listing_count: int, store_count: int) -> None:
    random.seed(7)
    with app.app_context():
        with get_connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            # Synthetic data: skip per-row user rows and FK checks while loading.
            connection.execute("PRAGMA foreign_keys=OFF")
            stores = [
                (index, f"فروشگاه {index}", CITIES[index % len(CITIES)], index)
                for index in range(1, store_count + 1)
            ]
            connection.executemany(
                "INSERT INTO stores (id, name, city, owner_id) VALUES (?, ?, ?, ?)", stores
            )
            listings = []
            for index in range(1, listing_count + 1):
                title = f"{random.choice(TITLE_WORDS)} {index}"
                listings.append((
                    index,
                    title,
                    random.choice(CATEGORIES),
                    random.choice(CITIES),
                    random.randint(10_000, 50_000_000),
                    f"توضیحات کالا {index} " + " ".join(random.sample(TITLE_WORDS, 3)),
                    "🛍️",
                    1 if index % 50 == 0 else 0,
                    random.randint(1, max(1, store_count)),
                    35.0 + random.random() * 3,
                    51.0 + random.random() * 3,
                ))
            connection.executemany(
                "INSERT INTO listings (id, title, category, city, price, description, emoji,"
                " featured, store_id, latitude, longitude)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                listings,
            )
            connection.execute(
                "INSERT INTO listings_fts (listings_fts) VALUES ('rebuild')"
            )


def measure(name: str, callback, repeats: int) -> dict:
    callback()  # warm caches
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        callback()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    return {
        "endpoint": name,
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95) - 1)], 2),
        "min_ms": round(samples[0], 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listings", type=int, default=1_000_000)
    parser.add_argument("--stores", type=int, default=100_000)
    parser.add_argument("--repeat", type=int, default=25)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "probe-secret",
                "DATABASE_PATH": str(Path(tmp) / "scale.sqlite3"),
                "UPLOAD_FOLDER": str(Path(tmp) / "uploads"),
            }
        )
        with app.app_context():
            initialize_database()
        started = time.perf_counter()
        build(app, args.listings, args.stores)
        build_seconds = time.perf_counter() - started
        client = app.test_client()
        client.get("/")  # warm template caches

        results = [measure("GET /", lambda: client.get("/"), args.repeat)]
        results.append(measure(
            "GET /api/listings (page 1)",
            lambda: client.get("/api/listings?limit=50"),
            args.repeat,
        ))
        results.append(measure(
            "GET /api/listings (deep page)",
            lambda: client.get(f"/api/listings?limit=50&before_id={args.listings - 5000}"),
            args.repeat,
        ))
        results.append(measure(
            "GET /api/listings?q=دوچرخه",
            lambda: client.get("/api/listings?limit=50&q=دوچرخه"),
            args.repeat,
        ))
        results.append(measure(
            "GET /api/listings?city+category",
            lambda: client.get("/api/listings?limit=50&city=تهران&category=digital"),
            args.repeat,
        ))
        results.append(measure(
            "GET /api/listings nearby",
            lambda: client.get("/api/listings?lat=35.7&lon=51.4&radius_km=10"),
            args.repeat,
        ))
        results.append(measure(
            "GET /api/stores",
            lambda: client.get("/api/stores?limit=50"),
            args.repeat,
        ))
        results.append(measure(
            "GET /sitemap.xml",
            lambda: client.get("/sitemap.xml"),
            5,
        ))

    print(json.dumps({"listings": args.listings, "stores": args.stores,
                      "seed_seconds": round(build_seconds, 1), "results": results},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
