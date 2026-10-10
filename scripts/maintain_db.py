#!/usr/bin/env python3
"""Database maintenance for a large catalogue.

Safe to run against the live database (every step is online and non-destructive
except `--vacuum`, which rewrites the file and needs free disk space equal to
roughly the database size).

    python scripts/maintain_db.py                 # ANALYZE + optimize + checkpoint
    python scripts/maintain_db.py --report        # size and row counts only
    python scripts/maintain_db.py --vacuum        # (off-hours) reclaim free pages

Why `ANALYZE` matters: SQLite chooses query plans from statistics in the
`sqlite_stat1` table. Without them it guesses, and on a million-row catalogue a
bad guess turns a 0.2 ms index seek into a 250 ms scan. The app never runs
ANALYZE on its own because on a huge table the scan costs seconds; run it from
cron (weekly is plenty) or after a bulk import.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TABLES = ("listings", "stores", "users", "store_follows", "saved_products",
          "conversations", "messages", "content_reports", "monetization_orders",
          "listing_tags", "support_tickets")


def report(connection: sqlite3.Connection) -> None:
    database_path = Path(connection.execute("PRAGMA database_list").fetchone()[2])
    size_mb = database_path.stat().st_size / 1_048_576 if database_path.is_file() else 0.0
    print(f"database : {database_path} ({size_mb:.1f} MiB)")
    page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    free_pages = connection.execute("PRAGMA freelist_count").fetchone()[0]
    print(f"pages    : {page_count} used, {free_pages} free "
          f"({free_pages / max(1, page_count):.0%} reclaimable)")
    for table in TABLES:
        try:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.Error:
            continue  # table not created yet
        print(f"  {table:20s} {count:>12,}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get("DATABASE_PATH", str(ROOT / "instance" / "kidareh.sqlite3")),
    )
    parser.add_argument("--report", action="store_true", help="print size and row counts, change nothing")
    parser.add_argument("--vacuum", action="store_true", help="rewrite the file to reclaim free pages")
    args = parser.parse_args()

    source = Path(args.database).expanduser().resolve()
    if not source.is_file():
        print(f"Database file not found: {source}", file=sys.stderr)
        return 2

    try:
        connection = sqlite3.connect(source, timeout=60)
    except sqlite3.Error as exc:
        print(f"Cannot open database: {exc}", file=sys.stderr)
        return 1

    try:
        connection.row_factory = sqlite3.Row
        if args.report:
            report(connection)
            return 0

        print("ANALYZE (query planner statistics)...", flush=True)
        connection.execute("ANALYZE")
        print("PRAGMA optimize (index recommendations)...", flush=True)
        connection.execute("PRAGMA optimize")
        print("WAL checkpoint...", flush=True)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if args.vacuum:
            print("VACUUM (this rewrites the whole file)...", flush=True)
            connection.isolation_level = None
            connection.execute("VACUUM")
        connection.commit()
        report(connection)
        print("done")
        return 0
    except sqlite3.Error as exc:
        print(f"Maintenance failed: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
