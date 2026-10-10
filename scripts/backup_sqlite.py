#!/usr/bin/env python3
"""Create and verify a consistent SQLite backup."""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get("DATABASE_PATH", str(ROOT / "instance" / "kidareh.sqlite3")),
    )
    parser.add_argument("--output-dir", default=str(ROOT / "backups"))
    args = parser.parse_args()
    source = Path(args.database).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not source.is_file():
        print("Database file not found: " + str(source), file=sys.stderr)
        return 2

    # Microseconds avoid overwriting a backup when two runs start in one second.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = output_dir / ("kidareh-" + stamp + ".sqlite3")
    if destination == source:
        print("Backup destination must differ from the live database.", file=sys.stderr)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect("file:" + source.as_posix() + "?mode=ro", uri=True, timeout=30) as src:
            with sqlite3.connect(destination, timeout=30) as dst:
                src.backup(dst)
                integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise sqlite3.DatabaseError("Integrity check failed: " + str(integrity))
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except (sqlite3.Error, OSError) as exc:
        destination.unlink(missing_ok=True)
        print("Backup failed: " + str(exc), file=sys.stderr)
        return 1

    print("Backup verified: " + str(destination))
    print("Bytes: " + str(destination.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
