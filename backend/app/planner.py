"""Plan diario, racha, XP y estadísticas.

El plan mezcla cada día las piezas que la investigación muestra que funcionan:
repaso espaciado, input comprensible, práctica de producción en tareas reales,
entrenamiento del oído, pronunciación dirigida a tus sonidos débiles y fluidez.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from . import content, db, missions, srs


def streak(lang: str | None = None) -> dict:
    rows = db.query(
        "SELECT day, SUM(xp) AS xp FROM activity " + ("WHERE lang=? " if lang else "") + "GROUP BY day",
        (lang,) if lang else (),
    )
    days = {r["day"] for r in rows if (r["xp"] or 0) > 0}
    today = date.today()
    d = today if today.isoformat() in days else today - timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    # Mejor racha histórica
    best, cur, prev = 0, 0, None
    for day in sorted(days):
        dd = date.fromisoformat(day)
        cur = cur + 1 if prev and (dd - prev).days == 1 else 1
        best = max(best, cur)
        prev = dd
    return {"current": n, "best": best, "today_done": today.isoformat() in days}


def _today_kinds(lang: str) -> dict[str, dict]:
    rows = db.query(
        "SELECT kind, SUM(xp) AS xp, SUM(minutes) AS minutes, COUNT(*) AS n FROM activity "
        "WHERE lang=? AND day=? GROUP BY kind", (lang, db.today()))
    return {r["kind"]: r for r in rows}


def weak_phonemes(lang: str, limit: int = 5) -> list[dict]:
    rows = db.query("SELECT * FROM phoneme_stats WHERE lang=? AND attempts>=3", (lang,))
    out = []
    for r in rows:
        recent = json.loads(r["recent"] or "[]")
        avg = sum(recent) / len(recent) if recent else r["total"] / r["attempts"]
        out.append({"phoneme": r["phoneme"], "avg": round(avg, 1), "attempts": r["attempts"]})
    out.sort(key=lambda x: x["avg"])
    return [x for x in out if x["avg"] < 80][:limit]


def daily_plan(lang: str) -> dict:
    kinds = _today_kinds(lang)
    q = srs.queue(lang, limit=200)
    pron_today_n = db.one(
        "SELECT COUNT(*) AS n FROM activity WHERE lang=? AND day=? AND kind='pronunciation'",
        (lang, db.today()))["n"]
    weak = weak_phonemes(lang, 3)

    # Siguiente lección de gramática no completada
    done_lessons = {r["lesson_id"] for r in db.query(
        "SELECT lesson_id FROM grammar_progress WHERE lang=? AND completed IS NOT NULL", (lang,))}
    next_lesson = next((l for l in content.grammar(lang) if l["id"] not in done_lessons), None)

    # Siguiente misión desbloqueada sin completar
    next_mission = None
    for c in missions.list_missions(lang):
        for m in c["missions"]:
            if m["unlocked"] and not m["completed"]:
                next_mission = m
                break
        if next_mission:
            break

    tasks = []
    to_review = len(q["cards"])
    tasks.append({
        "id": "srs", "title": "Repaso espaciado",
        "detail": f"{to_review} tarjetas pendientes" if to_review else "Todo al día",
        "why": "Recordar activamente justo antes de olvidar fija la memoria a largo plazo.",
        "minutes": max(2, round(to_review * 0.15)), "route": "/repaso",
        "done": to_review == 0 and ("srs" in kinds or q["total"] > 0),
    })
    tasks.append({
        "id": "pronunciation", "title": "Pronunciación",
        "detail": ("Sonidos a trabajar: " + ", ".join(f"/{w['phoneme']}/" for w in weak)) if weak else "5 frases a tu nivel",
        "why": "Feedback inmediato por sonido corrige la pronunciación antes de que se fosilice.",
        "minutes": 5, "route": "/pronunciacion",
        "done": pron_today_n >= 5,
        "progress": f"{min(pron_today_n, 5)}/5",
    })
    tasks.append({
        "id": "listening", "title": "Entrena el oído",
        "detail": "Pares mínimos con voces y acentos distintos, o un dictado",
        "why": "Si no distingues un sonido al oírlo, no podrás producirlo. Varias voces generalizan mejor.",
        "minutes": 4, "route": "/oido",
        "done": "listening" in kinds or "dictation" in kinds,
    })
    if next_lesson:
        tasks.append({
            "id": "grammar", "title": "Gramática",
            "detail": f"{next_lesson['level']} · {next_lesson['title']}",
            "why": "Una explicación corta + práctica inmediata; los errores se convierten en tarjetas.",
            "minutes": 8, "route": f"/gramatica/{next_lesson['id']}",
            "done": "grammar" in kinds,
        })
    tasks.append({
        "id": "mission", "title": "Misión de inmersión",
        "detail": f"{next_mission['level']} · {next_mission['title']}" if next_mission else "Genera una misión nueva o conversa libremente",
        "why": "Usar el idioma para lograr algo real (tareas) es como lo entrenan las escuelas militares.",
        "minutes": 8,
        "route": f"/misiones?start={next_mission['id']}" if next_mission else "/misiones",
        "done": "mission" in kinds or "free_talk" in kinds,
    })
    tasks.append({
        "id": "input", "title": "Lectura / escucha",
        "detail": "Una historia a tu nivel con audio: toca cualquier palabra para traducirla y guardarla",
        "why": "El input comprensible (≈95-98 % de palabras conocidas) es el motor de la adquisición.",
        "minutes": 6, "route": "/lectura",
        "done": "reading" in kinds,
    })
    if date.today().toordinal() % 2 == 0:
        tasks.append({
            "id": "fluency", "title": "Fluidez",
            "detail": "Técnica 4/3/2 o lectura repetida cronometrada",
            "why": "Repetir con presión de tiempo sobre material conocido automatiza el habla.",
            "minutes": 9, "route": "/fluidez",
            "done": "fluency" in kinds,
        })

    xp_today = sum((k["xp"] or 0) for k in kinds.values())
    minutes_today = round(sum((k["minutes"] or 0) for k in kinds.values()), 1)
    goal = int(db.get_setting("daily_minutes", 20))
    return {
        "tasks": tasks,
        "done": sum(1 for t in tasks if t["done"]),
        "xp_today": xp_today,
        "minutes_today": minutes_today,
        "goal_minutes": goal,
        "streak": streak(),
        "srs": {k: q[k] for k in ("due", "new_available", "new_left_today", "total")},
    }


def stats(lang: str) -> dict:
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    rows = db.query(
        "SELECT day, SUM(xp) AS xp, SUM(minutes) AS minutes FROM activity WHERE lang=? AND day>=? GROUP BY day",
        (lang, days[0]))
    by_day = {r["day"]: r for r in rows}
    total = db.one("SELECT COALESCE(SUM(xp),0) AS xp, COALESCE(SUM(minutes),0) AS minutes FROM activity WHERE lang=?", (lang,))
    by_kind = db.query("SELECT kind, SUM(minutes) AS minutes, COUNT(*) AS n FROM activity WHERE lang=? GROUP BY kind", (lang,))
    pron = db.query(
        "SELECT substr(ts,1,10) AS day, AVG(score) AS avg, COUNT(*) AS n FROM pron_attempts WHERE lang=? "
        "AND ts >= ? GROUP BY day ORDER BY day", (lang, days[0]))
    mistakes = db.query(
        "SELECT category, COUNT(*) AS n FROM mistakes WHERE lang=? GROUP BY category ORDER BY n DESC", (lang,))
    missions_done = db.one("SELECT COUNT(*) AS n FROM mission_progress WHERE lang=? AND completed IS NOT NULL", (lang,))["n"]
    lessons_done = db.one("SELECT COUNT(*) AS n FROM grammar_progress WHERE lang=? AND completed IS NOT NULL", (lang,))["n"]
    known_words = db.one("SELECT COUNT(*) AS n FROM cards WHERE lang=? AND kind='word' AND state=2", (lang,))["n"]
    return {
        "days": [{"day": d, "xp": (by_day.get(d) or {}).get("xp") or 0,
                  "minutes": round((by_day.get(d) or {}).get("minutes") or 0, 1)} for d in days],
        "total_xp": total["xp"], "total_minutes": round(total["minutes"], 1),
        "by_kind": by_kind,
        "pronunciation_trend": pron,
        "weak_phonemes": weak_phonemes(lang, 8),
        "mistakes_by_category": mistakes,
        "missions_done": missions_done,
        "missions_total": sum(len(c["missions"]) for c in content.campaigns(lang)),
        "lessons_done": lessons_done,
        "lessons_total": len(content.grammar(lang)),
        "known_words": known_words,
        "vocab_total": len(content.vocab(lang)),
        "srs": srs.stats(lang),
        "streak": streak(),
    }
