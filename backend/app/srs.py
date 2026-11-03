"""Repetición espaciada con FSRS (el algoritmo moderno que usa Anki).

FSRS modela la memoria de cada tarjeta (estabilidad y dificultad) y programa el
repaso justo cuando la probabilidad de recordarla cae al 90 %. Frente a SM-2 hace
menos repasos para la misma retención.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

from . import db

_scheduler = Scheduler(desired_retention=0.9, enable_fuzzing=True)

RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add_card(lang: str, kind: str, front: str, back: str, extra: dict | None = None,
             source: str = "manual") -> int:
    """Crea una tarjeta nueva. Si ya existe (mismo idioma, tipo y frente) devuelve la existente."""
    front, back = front.strip(), back.strip()
    existing = db.one("SELECT id FROM cards WHERE lang=? AND kind=? AND front=?", (lang, kind, front))
    if existing:
        return existing["id"]
    card = Card()
    return db.execute(
        "INSERT INTO cards(lang, kind, front, back, extra, fsrs, due, state, source, created)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lang, kind, front, back, json.dumps(extra or {}, ensure_ascii=False),
         json.dumps(card.to_dict()), card.due.isoformat(), 0, source, db.now_iso()),
    )


def _row_to_card(row: dict) -> dict:
    out = dict(row)
    out["extra"] = json.loads(row["extra"] or "{}")
    fs = json.loads(row["fsrs"])
    out["stability"] = fs.get("stability")
    out["difficulty"] = fs.get("difficulty")
    out.pop("fsrs", None)
    return out


def new_cards_today(lang: str) -> int:
    row = db.one(
        "SELECT COUNT(*) AS n FROM review_log r JOIN cards c ON c.id=r.card_id "
        "WHERE r.lang=? AND substr(r.ts,1,10)=? AND r.id IN ("
        "  SELECT MIN(id) FROM review_log GROUP BY card_id)",
        (lang, datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    return row["n"] if row else 0


def queue(lang: str, limit: int = 50, kinds: list[str] | None = None) -> dict:
    """Tarjetas para estudiar ahora: las vencidas primero y luego nuevas (con tope diario)."""
    new_per_day = int(db.get_setting("new_cards_per_day", 15))
    now = _now().isoformat()
    kind_sql = ""
    params: list = [lang, now]
    if kinds:
        kind_sql = f" AND kind IN ({','.join('?' * len(kinds))})"
        params += kinds
    due = db.query(
        f"SELECT * FROM cards WHERE lang=? AND suspended=0 AND state>0 AND due<=?{kind_sql} "
        "ORDER BY due LIMIT ?",
        params + [limit],
    )
    remaining_new = max(0, new_per_day - new_cards_today(lang))
    # Los errores propios no cuentan para el tope de nuevas: son los más valiosos.
    mistakes_new = db.query(
        "SELECT * FROM cards WHERE lang=? AND suspended=0 AND state=0 AND kind='mistake' "
        "ORDER BY created LIMIT ?", (lang, limit))
    params_new: list = [lang]
    if kinds:
        params_new += kinds
    fresh = db.query(
        f"SELECT * FROM cards WHERE lang=? AND suspended=0 AND state=0 AND kind!='mistake'"
        f"{kind_sql} ORDER BY created LIMIT ?",
        params_new + [remaining_new],
    ) if remaining_new else []
    if kinds and "mistake" not in kinds:
        mistakes_new = []
    cards = [_row_to_card(r) for r in due + mistakes_new + fresh][:limit]
    counts = db.one(
        "SELECT SUM(CASE WHEN state>0 AND due<=? THEN 1 ELSE 0 END) AS due, "
        "SUM(CASE WHEN state=0 THEN 1 ELSE 0 END) AS new, COUNT(*) AS total "
        "FROM cards WHERE lang=? AND suspended=0",
        (now, lang),
    ) or {}
    return {
        "cards": cards,
        "due": counts.get("due") or 0,
        "new_available": counts.get("new") or 0,
        "new_left_today": remaining_new,
        "total": counts.get("total") or 0,
    }


def review(card_id: int, rating: str) -> dict:
    row = db.one("SELECT * FROM cards WHERE id=?", (card_id,))
    if not row:
        raise KeyError(card_id)
    card = Card.from_dict(json.loads(row["fsrs"]))
    card, _log = _scheduler.review_card(card, RATINGS.get(rating, Rating.Good), _now())
    # Estado propio: 0 = nunca vista. FSRS: 1 aprendiendo, 2 repaso, 3 reaprendiendo.
    state = int(card.state.value)
    db.execute(
        "UPDATE cards SET fsrs=?, due=?, state=? WHERE id=?",
        (json.dumps(card.to_dict()), card.due.isoformat(), state, card_id),
    )
    db.execute(
        "INSERT INTO review_log(card_id, lang, rating, ts) VALUES (?,?,?,?)",
        (card_id, row["lang"], int(RATINGS.get(rating, Rating.Good).value), db.now_iso()),
    )
    return {"id": card_id, "due": card.due.isoformat(), "state": state,
            "stability": card.stability, "difficulty": card.difficulty}


def retrievability(row: dict) -> float:
    try:
        card = Card.from_dict(json.loads(row["fsrs"]))
        return float(_scheduler.get_card_retrievability(card, _now()))
    except Exception:
        return 0.0


def stats(lang: str) -> dict:
    rows = db.query("SELECT state, kind, fsrs FROM cards WHERE lang=? AND suspended=0", (lang,))
    by_state = {"nuevas": 0, "aprendiendo": 0, "repaso": 0, "reaprendiendo": 0}
    names = ["nuevas", "aprendiendo", "repaso", "reaprendiendo"]
    mature = 0
    for r in rows:
        by_state[names[r["state"]]] += 1
        if r["state"] == 2:
            st = json.loads(r["fsrs"]).get("stability") or 0
            if st >= 21:
                mature += 1
    reviews = db.query(
        "SELECT rating FROM review_log WHERE lang=? AND ts >= datetime('now','-30 days')", (lang,))
    correct = sum(1 for r in reviews if r["rating"] > 1)
    return {
        "by_state": by_state,
        "total": len(rows),
        "mature": mature,  # estabilidad ≥ 21 días: palabras realmente asentadas
        "reviews_30d": len(reviews),
        "retention_30d": round(correct / len(reviews), 3) if reviews else None,
    }


def mastered(lang: str, limit: int = 60) -> list[dict]:
    """Tarjetas bien aprendidas (en repaso y con estabilidad ≥ 10 días) para fluidez."""
    rows = db.query(
        "SELECT * FROM cards WHERE lang=? AND state=2 AND suspended=0 AND kind IN ('word','sentence','phrase')",
        (lang,),
    )
    out = []
    for r in rows:
        if (json.loads(r["fsrs"]).get("stability") or 0) >= 10:
            out.append(_row_to_card(r))
    return out[:limit]
