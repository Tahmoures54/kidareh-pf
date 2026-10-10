import sqlite3
import sys

from scripts.restore_sqlite import main


def _write_sample_database(path, value):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sample(value TEXT)")
        db.execute("INSERT INTO sample VALUES(?)", (value,))


def test_restore_preserves_previous_database(tmp_path, monkeypatch):
    source, target = tmp_path / "backup.sqlite3", tmp_path / "live.sqlite3"
    _write_sample_database(source, "new")
    _write_sample_database(target, "old")

    monkeypatch.setattr(
        sys, "argv", ["restore_sqlite.py", "--backup", str(source), "--database", str(target)]
    )
    assert main() == 2

    monkeypatch.setattr(
        sys,
        "argv",
        ["restore_sqlite.py", "--backup", str(source), "--database", str(target), "--yes"],
    )
    assert main() == 0

    with sqlite3.connect(target) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "new"
    safety_copies = list(tmp_path.glob("live.sqlite3.pre-restore-*"))
    assert len(safety_copies) == 1
    with sqlite3.connect(safety_copies[0]) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "old"


def test_restore_rejects_corrupt_backup_without_touching_live_database(tmp_path, monkeypatch):
    source, target = tmp_path / "corrupt.sqlite3", tmp_path / "live.sqlite3"
    source.write_bytes(b"this is not a SQLite database")
    _write_sample_database(target, "keep-me")

    monkeypatch.setattr(
        sys,
        "argv",
        ["restore_sqlite.py", "--backup", str(source), "--database", str(target), "--yes"],
    )
    assert main() == 2

    with sqlite3.connect(target) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "keep-me"
    assert not list(tmp_path.glob("live.sqlite3.pre-restore-*"))


def test_restore_rejects_missing_backup_cleanly(tmp_path, monkeypatch):
    target = tmp_path / "live.sqlite3"
    _write_sample_database(target, "keep-me")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "restore_sqlite.py",
            "--backup",
            str(tmp_path / "missing.sqlite3"),
            "--database",
            str(target),
            "--yes",
        ],
    )
    assert main() == 2
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "keep-me"
