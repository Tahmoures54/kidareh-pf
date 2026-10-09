import sqlite3,sys
from scripts.restore_sqlite import main

def test_restore_preserves_previous_database(tmp_path,monkeypatch):
    src,dst=tmp_path/'backup.sqlite3',tmp_path/'live.sqlite3'
    for path,value in ((src,'new'),(dst,'old')):
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE sample(value TEXT)');db.execute('INSERT INTO sample VALUES(?)',(value,))
    monkeypatch.setattr(sys,'argv',['restore_sqlite.py','--backup',str(src),'--database',str(dst)])
    assert main()==2
    monkeypatch.setattr(sys,'argv',['restore_sqlite.py','--backup',str(src),'--database',str(dst),'--yes'])
    assert main()==0
    with sqlite3.connect(dst) as db:assert db.execute('SELECT value FROM sample').fetchone()[0]=='new'
    safety=list(tmp_path.glob('live.sqlite3.pre-restore-*'));assert len(safety)==1
    with sqlite3.connect(safety[0]) as db:assert db.execute('SELECT value FROM sample').fetchone()[0]=='old'