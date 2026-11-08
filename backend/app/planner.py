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

    level = db.get_setting(f"level_{lang}", "A1")
    advanced = level in ("B1", "B2", "C1")
    reviewed_today = db.one(
        "SELECT COUNT(*) AS n FROM activity WHERE lang=? AND day=? AND kind='srs'", (lang, db.today()))["n"]
    to_review = len(q["cards"])

    def n(k):  # actividades de ese tipo hoy
        return (kinds.get(k) or {}).get("n") or 0

    def task(id_, title, goal, cur, target, detail, why, minutes, route, core=True):
        cur = min(cur, target)
        return {"id": id_, "title": title, "goal": goal, "current": cur, "target": target,
                "progress": f"{cur}/{target}", "done": cur >= target, "detail": detail, "why": why,
                "minutes": minutes, "route": route, "core": core}

    tasks = [
        task("srs", "Repaso espaciado", "Repasar todas las tarjetas pendientes",
             reviewed_today, max(1, reviewed_today + to_review),
             f"{to_review} tarjetas pendientes ahora" if to_review else "¡Todo al día!",
             "Recordar activamente justo antes de olvidar fija la memoria a largo plazo.",
             max(2, round(to_review * 0.15)), "/repaso"),
        task("pronunciation", "Pronunciación", "Practicar 5 frases",
             pron_today_n, 5,
             ("Sonidos a trabajar: " + ", ".join(f"/{w['phoneme']}/" for w in weak)) if weak else "Frases a tu nivel",
             "Feedback inmediato por sonido corrige la pronunciación antes de que se fosilice.", 5, "/pronunciacion"),
        task("listening", "Escucha activa", "1 audio, pares mínimos o dictado",
             n("listening") + n("dictation"), 1,
             "Un diálogo o pódcast a tu nivel + resumen" if advanced else "Pares mínimos con varias voces, o un dictado",
             "Entender a nativos a velocidad real es lo que más cuesta para llegar a C1.", 7 if advanced else 4, "/oido"),
        task("mission", "Misión o conversación", "Terminar 1 misión o conversación (hasta el informe)",
             n("mission") + n("free_talk"), 1,
             f"Siguiente: {next_mission['level']} · {next_mission['title']}" if next_mission else
             ("Debate, entrevista o 'explícamelo'" if advanced else "Genera una misión nueva o conversa libremente"),
             "Usar el idioma para lograr algo real es como lo entrenan las escuelas militares.", 8,
             f"/misiones?start={next_mission['id']}" if next_mission else "/misiones"),
    ]
    if next_lesson:
        tasks.append(task("grammar", "Gramática", "Hacer 1 lección", n("grammar"), 1,
                          f"Siguiente: {next_lesson['level']} · {next_lesson['title']}",
                          "Explicación corta + práctica inmediata; tus errores pasan al repaso.", 8,
                          f"/gramatica/{next_lesson['id']}", core=False))
    tasks.append(task("input", "Lectura", "Leer 1 texto y responder", n("reading"), 1,
                      "Una historia a tu nivel o un texto tuyo importado",
                      "El input comprensible es el motor de la adquisición.", 6, "/lectura", core=False))
    tasks.append(task("fluency", "Fluidez", "1 sesión (4/3/2 o lectura repetida)", n("fluency"), 1,
                      "Habla lo mismo cada vez más rápido", "Automatiza el habla con material que ya conoces.",
                      9, "/fluidez", core=False))

    # Medir el nivel cada ~3 semanas (o la primera vez) para ver el progreso real hacia C1.
    last = db.one("SELECT ts FROM assessments WHERE lang=? AND skill IN ('vocabulary','speaking','writing') ORDER BY id DESC LIMIT 1", (lang,))
    stale = (not last) or (date.today() - date.fromisoformat(last["ts"][:10])).days >= 21
    if stale:
        tasks.append(task("assessment", "Mide tu nivel", "1 prueba de nivel", n("assessment"), 1,
                          "Test de vocabulario y prueba oral/escrita" if not last else "Han pasado 3 semanas: vuelve a medir",
                          "Medir cada destreza muestra qué te frena para llegar a C1.", 6, "/nivel", core=False))

    xp_today = sum((k["xp"] or 0) for k in kinds.values())
    minutes_today = round(sum((k["minutes"] or 0) for k in kinds.values()), 1)
    goal = int(db.get_setting("daily_minutes", 20))
    core = [t for t in tasks if t["core"]]
    core_done = sum(1 for t in core if t["done"])
    # El día cuenta como completado si haces las 4 esenciales o alcanzas tu objetivo de minutos.
    day_complete = core_done == len(core) or minutes_today >= goal
    return {
        "tasks": tasks,
        "done": sum(1 for t in tasks if t["done"]),
        "core_done": core_done, "core_total": len(core),
        "day_complete": day_complete,
        "xp_today": xp_today,
        "minutes_today": minutes_today,
        "goal_minutes": goal,
        "streak": streak(),
        "today_log": today_log(lang),
        "srs": {k: q[k] for k in ("due", "new_available", "new_left_today", "total")},
    }


KIND_ES = {"srs": "Repaso", "pronunciation": "Pronunciación", "listening": "Escucha", "dictation": "Dictado",
           "grammar": "Gramática", "mission": "Misión", "free_talk": "Conversación", "reading": "Lectura",
           "writing": "Escritura", "fluency": "Fluidez", "assessment": "Prueba de nivel"}


def today_log(lang: str) -> list[dict]:
    """Lo que ya hiciste hoy (para que veas qué ha contado)."""
    rows = db.query("SELECT kind, COUNT(*) AS n, SUM(xp) AS xp, SUM(minutes) AS minutes FROM activity "
                    "WHERE lang=? AND day=? GROUP BY kind ORDER BY MIN(id)", (lang, db.today()))
    return [{"kind": r["kind"], "name": KIND_ES.get(r["kind"], r["kind"]), "n": r["n"],
             "xp": r["xp"] or 0, "minutes": round(r["minutes"] or 0, 1)} for r in rows]


LEVELS_ALL = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _snapshot(lang: str) -> dict:
    from . import assessment
    words = db.one("SELECT COUNT(*) AS n FROM cards WHERE lang=? AND kind IN ('word','phrase') AND state=2", (lang,))["n"]
    missions_done = db.one("SELECT COUNT(*) AS n FROM mission_progress WHERE lang=? AND completed IS NOT NULL", (lang,))["n"]
    lessons_done = db.one("SELECT COUNT(*) AS n FROM grammar_progress WHERE lang=? AND completed IS NOT NULL", (lang,))["n"]
    pron = db.one("SELECT AVG(score) AS a FROM (SELECT score FROM pron_attempts WHERE lang=? ORDER BY id DESC LIMIT 30)", (lang,))["a"]
    summ = assessment.summary(lang)
    return {
        "date": db.today(),
        "level": db.get_setting(f"level_{lang}", "A1"),
        "overall": summ["overall"],
        "skills": {k: (v or {}).get("level") for k, v in summ["skills"].items()},
        "vocab_size": (summ["skills"].get("vocabulary") or {}).get("size"),
        "words_known": words, "missions_done": missions_done, "lessons_done": lessons_done,
        "pronunciation": round(pron, 1) if pron else None,
        "total_minutes": round(db.one("SELECT COALESCE(SUM(minutes),0) AS m FROM activity WHERE lang=?", (lang,))["m"]),
    }


def journey(lang: str) -> dict:
    """Punto de partida vs ahora, semanas e hitos: para ver claramente si avanzas."""
    key = f"baseline_{lang}"
    base = db.get_setting(key)
    now = _snapshot(lang)
    if not base:
        # Punto de partida = tu primer día de uso (si ya habías practicado, se reconstruye desde el historial).
        first_day = db.one("SELECT MIN(day) AS d FROM activity WHERE lang=?", (lang,))["d"]
        base = {**now, "date": first_day or db.today(), "overall": None,
                "skills": {k: None for k in now["skills"]}, "vocab_size": None,
                "words_known": 0, "missions_done": 0, "lessons_done": 0, "total_minutes": 0,
                "pronunciation": None}
        db.set_setting(key, base)
    # Si el punto de partida no tenía una destreza medida, usamos la PRIMERA medición de esa destreza.
    changed = False
    for skill in ("vocabulary", "speaking", "writing"):
        if not base["skills"].get(skill):
            first = db.one("SELECT level, score FROM assessments WHERE lang=? AND skill=? ORDER BY id LIMIT 1", (lang, skill))
            if first:
                base["skills"][skill] = first["level"]
                if skill == "vocabulary" and not base.get("vocab_size"):
                    base["vocab_size"] = round(first["score"])
                changed = True
    if not base.get("pronunciation"):
        first = db.one("SELECT AVG(score) AS a FROM (SELECT score FROM pron_attempts WHERE lang=? ORDER BY id LIMIT 10)", (lang,))
        if first and first["a"]:
            base["pronunciation"] = round(first["a"], 1)
            changed = True
    if changed:
        db.set_setting(key, base)

    # Semanas (lunes a domingo): días activos, minutos y XP.
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for w in range(7, -1, -1):
        start = monday - timedelta(weeks=w)
        end = start + timedelta(days=6)
        r = db.one("SELECT COUNT(DISTINCT day) AS d, COALESCE(SUM(minutes),0) AS m, COALESCE(SUM(xp),0) AS xp "
                   "FROM activity WHERE lang=? AND day BETWEEN ? AND ?", (lang, start.isoformat(), end.isoformat()))
        weeks.append({"start": start.isoformat(), "days": r["d"], "minutes": round(r["m"]), "xp": r["xp"]})
    this_week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        r = db.one("SELECT COALESCE(SUM(minutes),0) AS m FROM activity WHERE lang=? AND day=?", (lang, d.isoformat()))
        this_week.append({"day": d.isoformat(), "minutes": round(r["m"], 1), "future": d > today, "today": d == today})

    cur = now["overall"] or now["level"]
    c1 = LEVELS_ALL.index("C1")
    pct = round(100 * (LEVELS_ALL.index(cur) + 1) / (c1 + 1)) if cur in LEVELS_ALL else 0

    def ms(title, cur_v, target):
        return {"title": title, "current": min(cur_v, target), "target": target, "done": cur_v >= target}
    milestones = [
        ms("Primera misión completada", now["missions_done"], 1),
        ms("100 palabras dominadas", now["words_known"], 100),
        ms("10 lecciones de gramática", now["lessons_done"], 10),
        ms("500 palabras dominadas", now["words_known"], 500),
        ms("10 misiones completadas", now["missions_done"], 10),
        ms("1.000 palabras dominadas", now["words_known"], 1000),
        ms("50 horas de práctica", now["total_minutes"] // 60, 50),
        ms("2.500 palabras dominadas", now["words_known"], 2500),
    ]
    return {"baseline": base, "now": now, "current_level": cur, "c1_progress": pct, "weeks": weeks,
            "this_week": this_week, "milestones": milestones,
            "goal_minutes": int(db.get_setting("daily_minutes", 20))}


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
