"""Base de datos SQLite: un solo archivo (data/speech.db) con todo tu progreso."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from .config import DB_PATH

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Tarjetas de repaso (FSRS). kind: word | sentence | mistake | phrase
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    kind TEXT NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    fsrs TEXT NOT NULL,
    due TEXT NOT NULL,
    state INTEGER NOT NULL DEFAULT 0,      -- 0 nueva, 1 aprendiendo, 2 repaso, 3 reaprendiendo
    source TEXT NOT NULL DEFAULT 'manual',
    suspended INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    UNIQUE(lang, kind, front)
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(lang, suspended, due);

CREATE TABLE IF NOT EXISTS review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    lang TEXT NOT NULL,
    rating INTEGER NOT NULL,
    ts TEXT NOT NULL
);

-- Registro de actividad: alimenta XP, racha y estadísticas.
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    kind TEXT NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    minutes REAL NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '{}',
    day TEXT NOT NULL,
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_day ON activity(lang, day);

-- Errores detectados (chat, misiones, escritura, gramática): tu "cuaderno de errores".
CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    source TEXT NOT NULL,
    original TEXT NOT NULL,
    corrected TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'otro',
    card_id INTEGER,
    ts TEXT NOT NULL
);

-- Estadística acumulada por fonema (qué sonidos te cuestan más).
CREATE TABLE IF NOT EXISTS phoneme_stats (
    lang TEXT NOT NULL,
    phoneme TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    recent TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (lang, phoneme)
);

CREATE TABLE IF NOT EXISTS pron_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    text TEXT NOT NULL,
    score REAL NOT NULL,
    mode TEXT NOT NULL DEFAULT 'practice',
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grammar_progress (
    lang TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    best_score REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    completed TEXT,
    PRIMARY KEY (lang, lesson_id)
);

CREATE TABLE IF NOT EXISTS custom_missions (
    id TEXT PRIMARY KEY,
    lang TEXT NOT NULL,
    data TEXT NOT NULL,
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mission_progress (
    lang TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    best_score REAL NOT NULL DEFAULT 0,
    runs INTEGER NOT NULL DEFAULT 0,
    completed TEXT,
    PRIMARY KEY (lang, mission_id)
);

CREATE TABLE IF NOT EXISTS mission_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    mission TEXT NOT NULL,
    transcript TEXT NOT NULL DEFAULT '[]',
    state TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    started TEXT NOT NULL,
    finished TEXT
);

CREATE TABLE IF NOT EXISTS fluency_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    kind TEXT NOT NULL,
    data TEXT NOT NULL,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang TEXT NOT NULL,
    level TEXT NOT NULL,
    title TEXT NOT NULL,
    data TEXT NOT NULL,
    read_done INTEGER NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);

-- Caché de traducciones rápidas (tocar una palabra/frase para traducir).
CREATE TABLE IF NOT EXISTS translations (
    lang TEXT NOT NULL,
    text TEXT NOT NULL,
    result TEXT NOT NULL,
    PRIMARY KEY (lang, text)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> str:
    # Día LOCAL del usuario: la racha se cuenta según su reloj, no UTC.
    return datetime.now().strftime("%Y-%m-%d")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    with _lock:
        cur = conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def one(sql: str, params: tuple | list = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | list = ()) -> int:
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur.lastrowid or 0


def get_setting(key: str, default: Any = None) -> Any:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value: Any) -> None:
    execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )


def log_activity(lang: str, kind: str, xp: int = 0, minutes: float = 0, detail: dict | None = None):
    execute(
        "INSERT INTO activity(lang, kind, xp, minutes, detail, day, ts) VALUES (?,?,?,?,?,?,?)",
        (lang, kind, xp, minutes, json.dumps(detail or {}, ensure_ascii=False), today(), now_iso()),
    )


def log_mistake(lang: str, source: str, original: str, corrected: str,
                explanation: str = "", category: str = "otro") -> int:
    """Guarda un error y crea automáticamente una tarjeta de repaso para él."""
    from . import srs  # import diferido para evitar ciclos

    original = (original or "").strip()
    corrected = (corrected or "").strip()
    if not original or not corrected or original.lower() == corrected.lower():
        return 0
    card_id = srs.add_card(
        lang, "mistake", front=original, back=corrected,
        extra={"explanation": explanation, "category": category}, source=source,
    )
    return execute(
        "INSERT INTO mistakes(lang, source, original, corrected, explanation, category, card_id, ts)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (lang, source, original, corrected, explanation, category, card_id, now_iso()),
    )
