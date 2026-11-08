"""Copias de seguridad de tu progreso (data/speech.db).

- Una copia por día (se actualiza mientras usas la app) en tu carpeta Documentos, fuera del
  proyecto: si borras o reinstalas la app, tu progreso sigue ahí. Se guardan los últimos 30 días.
- Se puede descargar una copia y restaurar cualquiera desde Ajustes (antes de restaurar se
  guarda automáticamente una copia del estado actual).
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path

from . import db
from .config import DATA_DIR, DB_PATH

log = logging.getLogger("backup")
KEEP_DAYS = 30
INTERVAL_SEC = 2 * 3600


def _documents_dir() -> Path:
    """Carpeta 'Documentos' real de Windows (puede estar redirigida a otra unidad u OneDrive)."""
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def backup_dir() -> Path:
    custom = os.getenv("BACKUP_DIR")
    d = Path(custom) if custom else _documents_dir() / "Speech V2 - copias de seguridad"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        d = DATA_DIR / "backups"  # respaldo si Documentos no es accesible
        d.mkdir(parents=True, exist_ok=True)
        return d


def make_backup(suffix: str = "") -> Path:
    """Copia consistente de la base de datos (API de backup de SQLite, segura con la app abierta)."""
    name = f"speech-{date.today().isoformat()}{suffix}.db"
    target = backup_dir() / name
    tmp = target.with_suffix(".tmp")
    with db._lock:
        dst = sqlite3.connect(tmp)
        db.conn().backup(dst)
        dst.close()
    os.replace(tmp, target)
    _prune()
    return target


def _prune():
    files = sorted(backup_dir().glob("speech-*.db"))
    daily = [f for f in files if len(f.stem) == len("speech-2026-01-01")]
    for f in daily[:-KEEP_DAYS]:
        try:
            f.unlink()
        except OSError:
            pass


def list_backups() -> list[dict]:
    out = []
    for f in sorted(backup_dir().glob("speech-*.db"), reverse=True):
        st = f.stat()
        out.append({"name": f.name, "size_kb": round(st.st_size / 1024),
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")})
    return out


def restore(name: str) -> None:
    src = backup_dir() / name
    if not src.exists() or not name.startswith("speech-") or "/" in name or "\\" in name:
        raise FileNotFoundError(name)
    make_backup(suffix="-antes-de-restaurar")
    with db._lock:
        s = sqlite3.connect(src)
        s.backup(db.conn())
        s.close()


def start_scheduler():
    def loop():
        while True:
            try:
                p = make_backup()
                log.info("Copia de seguridad guardada en %s", p)
            except Exception as e:  # nunca debe tumbar la app
                log.warning("No se pudo hacer la copia de seguridad: %s", e)
            time.sleep(INTERVAL_SEC)
    threading.Thread(target=loop, daemon=True).start()


def export_copy() -> Path:
    """Copia para descargar desde el navegador."""
    out = DATA_DIR / f"speech-export-{datetime.now().strftime('%Y%m%d-%H%M')}.db"
    with db._lock:
        dst = sqlite3.connect(out)
        db.conn().backup(dst)
        dst.close()
    return out
