#!/usr/bin/env python3
"""Validate a SQLite backup and safely restore it, preserving the current DB."""
import argparse, os, shutil, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

def check(path):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True,timeout=30) as db:return db.execute('PRAGMA integrity_check').fetchone()[0]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--backup',required=True);p.add_argument('--database',default=os.environ.get('DATABASE_PATH','instance/kidareh.sqlite3'));p.add_argument('--yes',action='store_true');a=p.parse_args();src=Path(a.backup).expanduser().resolve();dst=Path(a.database).expanduser().resolve()
    if not src.is_file() or check(src)!='ok':print('Backup missing or invalid.',file=sys.stderr);return 2
    if src==dst:print('Backup and target must differ.',file=sys.stderr);return 2
    if dst.exists() and not a.yes:print('Target exists; rerun with --yes after stopping the app.',file=sys.stderr);return 2
    dst.parent.mkdir(parents=True,exist_ok=True);safety=None
    if dst.exists():safety=dst.with_name(dst.name+'.pre-restore-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));shutil.copy2(dst,safety)
    temp=dst.with_name(dst.name+'.restore-tmp')
    try:
        with sqlite3.connect(src) as s,sqlite3.connect(temp) as d:s.backup(d)
        if check(temp)!='ok':raise sqlite3.DatabaseError('integrity_check failed')
        os.replace(temp,dst)
    except (OSError,sqlite3.Error) as e:temp.unlink(missing_ok=True);print('Restore failed: '+str(e),file=sys.stderr);return 1
    try:dst.chmod(0o600)
    except OSError:pass
    print('Restore verified: '+str(dst))
    if safety:print('Previous database preserved: '+str(safety))
    return 0
if __name__=='__main__':raise SystemExit(main())