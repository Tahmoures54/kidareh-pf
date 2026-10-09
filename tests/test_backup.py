import sqlite3
import sys

from scripts.backup_sqlite import main


def test_backup_sqlite_creates_verified_copy(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('persisted')")
    output = tmp_path / "safe-backups"
    monkeypatch.setattr(sys, "argv", ["backup_sqlite.py", "--database", str(source), "--output-dir", str(output)])

    assert main() == 0
    backups = list(output.glob("kidareh-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "persisted"


def test_backup_sqlite_reports_missing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["backup_sqlite.py", "--database", str(tmp_path / "missing.sqlite3"), "--output-dir", str(tmp_path / "backups")])
    assert main() == 2
