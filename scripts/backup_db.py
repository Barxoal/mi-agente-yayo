#!/usr/bin/env python3
"""Backup consistente de niah_history.db con rotación."""
import gzip
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROYECTO = Path.home() / "mi-agente-llama"
DB = PROYECTO / "niah_history.db"
BACKUP_DIR = PROYECTO / "backups"
LOG = BACKUP_DIR / "backup.log"
RETENER = 30


def log(msg: str) -> None:
    linea = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(linea, flush=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def main() -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB.exists():
        log(f"ERROR: no existe {DB}")
        return 1

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    tmp_db = BACKUP_DIR / f".tmp_{ts}.db"
    dest = BACKUP_DIR / f"niah_history_{ts}.db.gz"

    # Backup consistente vía API sqlite3.backup() (funciona con DB en uso)
    try:
        src = sqlite3.connect(str(DB))
        dst = sqlite3.connect(str(tmp_db))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        log(f"ERROR: backup falló: {e}")
        tmp_db.unlink(missing_ok=True)
        return 1

    # Comprimir
    try:
        with tmp_db.open("rb") as fin, gzip.open(dest, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    finally:
        tmp_db.unlink(missing_ok=True)

    log(f"OK: {dest.name} ({dest.stat().st_size} bytes)")

    # Rotación: mantener las últimas RETENER
    backups = sorted(
        BACKUP_DIR.glob("niah_history_*.db.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for viejo in backups[RETENER:]:
        viejo.unlink()
        log(f"Rotado: {viejo.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
