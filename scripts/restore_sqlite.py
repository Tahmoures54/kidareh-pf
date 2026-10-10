#!/usr/bin/env python3
"""Validate a SQLite backup and safely restore it, preserving the current DB."""
import argparse
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def is_valid_database(path: Path) -> bool:
    """Return False instead of crashing when the backup is missing or malformed."""
    try:
        with sqlite3.connect(
            "file:" + path.as_posix() + "?mode=ro", uri=True, timeout=30
        ) as db:
            result = db.execute("PRAGMA integrity_check").fetchone()
        return bool(result and result[0] == "ok")
    except (OSError, sqlite3.Error, ValueError):
        return False


def create_safety_backup(source_path: Path, safety_path: Path) -> None:
    """Take a transactionally consistent copy, including committed WAL content."""
    with sqlite3.connect(source_path, timeout=30) as source:
        with sqlite3.connect(safety_path, timeout=30) as destination:
            source.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("Safety backup integrity check failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True)
    parser.add_argument(
        "--database",
        default=os.environ.get("DATABASE_PATH", "instance/kidareh.sqlite3"),
    )
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    source = Path(args.backup).expanduser().resolve()
    target = Path(args.database).expanduser().resolve()

    if not source.is_file() or not is_valid_database(source):
        print("Backup missing or invalid.", file=sys.stderr)
        return 2
    if source == target:
        print("Backup and target must differ.", file=sys.stderr)
        return 2
    if target.exists() and not args.yes:
        print("Target exists; rerun with --yes after stopping the app.", file=sys.stderr)
        return 2

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Create the temporary file beside the target so os.replace stays atomic.
        fd, temp_name = tempfile.mkstemp(
            prefix=target.name + ".restore-", suffix=".tmp", dir=target.parent
        )
        os.close(fd)
        temp = Path(temp_name)
        temp.unlink()
    except OSError as exc:
        print("Could not prepare restore destination: " + str(exc), file=sys.stderr)
        return 1

    safety = None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        with sqlite3.connect(source, timeout=30) as backup_db:
            with sqlite3.connect(temp, timeout=30) as restored_db:
                backup_db.backup(restored_db)
                result = restored_db.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise sqlite3.DatabaseError("Restored database integrity check failed")

        if target.exists():
            safety = target.with_name(target.name + ".pre-restore-" + stamp)
            create_safety_backup(target, safety)
            try:
                safety.chmod(0o600)
            except OSError:
                pass

        # A stopped SQLite app can still leave WAL sidecars. Remove them only
        # after a verified restore and a verified safety copy have been made.
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(target) + suffix)
            if sidecar.exists():
                sidecar.unlink()

        os.replace(temp, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass
    except (OSError, sqlite3.Error) as exc:
        temp.unlink(missing_ok=True)
        Path(str(temp) + "-wal").unlink(missing_ok=True)
        Path(str(temp) + "-shm").unlink(missing_ok=True)
        print("Restore failed: " + str(exc), file=sys.stderr)
        if safety:
            print("Previous database safety copy: " + str(safety), file=sys.stderr)
        return 1

    print("Restore verified: " + str(target))
    if safety:
        print("Previous database preserved: " + str(safety))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
