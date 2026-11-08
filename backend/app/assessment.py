"""Evaluación de nivel (MCER/CEFR) por destreza: vocabulario, expresión oral, escritura y comprensión.

- Vocabulario: test de tamaño de vocabulario tipo "sí/no" por franjas de frecuencia, con
  pseudopalabras para corregir la tendencia a decir "sí" a todo (como X-Lex / LexTALE).
  La relación tamaño ↔ nivel sigue la estimación de Milton (2010) sobre las 5.000 palabras
  más frecuentes: A1 <1.500 · A2 1.500-2.500 · B1 2.750-3.250 · B2 3.250-3.750 · C1 3.750-4.500 · C2 >4.500.
- Expresión oral y escritura: la IA evalúa con los descriptores del MCER y criterios tipo Cambridge,
  combinados con medidas objetivas (palabras por minuto, pausas y pronunciación por fonema).
- Comprensión: se estima con tus resultados en Escucha y Lectura según el nivel del material.
"""
from __future__ import annotations

import json
import random
import re

from . import content, db, llm

from .config import TARGET_NAMES as TARGET
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

PSEUDO = {
    "en": ["plontish", "fendle", "crumbish", "sporrow", "drimble", "proctive", "wember", "glime", "bleave", "strimp",
           "morlent", "quanish", "tamble", "sprelling", "ganderous", "wistle", "plurnish", "dretch", "hobsome",
           "cranter", "mibble", "fopular", "spadge", "norable", "gristen", "voltary", "blunch", "skirple"],
    "fr": ["chapoir", "frocule", "mautrer", "pelinade", "gourmir", "tralacer", "vitresque", "bouchenard", "plinter",
           "dravoir", "esclumer", "fanoir", "grisenne", "pralier", "trouvelle", "cramoise", "bablir", "pontaison",
           "sourniche", "fréquir", "gamblot", "chavrir", "truniche", "plaudeur", "vernoir", "mescule", "glandoir"],
    "pt": ["brundeira", "chafolar", "trimenso", "galupar", "pernisco", "vontrado", "esbalir", "fornelha", "dramento",
           "quilhosa", "ralventar", "mofisco", "plenhada", "tursivo", "gramolar", "biscunha", "setroar", "fandilho",
           "cromeiro", "lapunça"],
    "de": ["Bruchtel", "verglamen", "Fenschung", "Knapotte", "stralmig", "Wunkerei", "Plimmer", "gesorbt", "Zwackel",
           "trunsen", "Molbung", "frastig", "kelpen", "Brodlung", "Wiepel", "flunsig", "Trampung"],
}
BAND = 1000
PER_BAND = 12
N_PSEUDO = 12


def _bare(word: str) -> str:
    """Quita el artículo alemán (das Haus → Haus) para que no delate cuáles son reales."""
    return re.sub(r"^(der|die|das) ", "", word)


def vocab_test(lang: str) -> dict:
    words = [_bare(w["word"]) for w in content.vocab(lang)]
    bands = []
    for b in range(0, min(len(words), 5000), BAND):
        pool = [w for w in words[b: b + BAND] if len(w) > 2]
        if len(pool) >= PER_BAND:
            bands.append(random.sample(pool, PER_BAND))
    pseudo = random.sample(PSEUDO[lang], min(N_PSEUDO, len(PSEUDO[lang])))
    items = [w for band in bands for w in band] + pseudo
    random.shuffle(items)
    return {"items": items, "bands": len(bands)}


def level_from_vocab(size: float) -> str:
    if size < 1500:
        return "A1"
    if size < 2500:
        return "A2"
    if size < 3250:
        return "B1"
    if size < 3750:
        return "B2"
    if size < 4500:
        return "C1"
    return "C2"


def score_vocab_test(lang: str, shown: list[str], known: list[str]) -> dict:
    words = [_bare(w["word"]) for w in content.vocab(lang)]
    rank = {w: i for i, w in enumerate(words)}
    pseudo = set(PSEUDO[lang])
    known_set = set(known)
    shown_pseudo = [w for w in shown if w in pseudo]
    false_alarm = (sum(1 for w in shown_pseudo if w in known_set) / len(shown_pseudo)) if shown_pseudo else 0
    bands: dict[int, list[bool]] = {}
    for w in shown:
        if w in rank:
            bands.setdefault(rank[w] // BAND, []).append(w in known_set)
    size = 0.0
    detail = []
    for b in sorted(bands):
        hit = sum(bands[b]) / len(bands[b])
        # Corrección por adivinación: (aciertos - falsas alarmas) / (1 - falsas alarmas)
        adj = max(0.0, (hit - false_alarm) / (1 - false_alarm)) if false_alarm < 1 else 0.0
        size += adj * BAND
        detail.append({"band": f"{b * BAND + 1}-{(b + 1) * BAND}", "known": round(hit * 100), "adjusted": round(adj * 100)})
    level = level_from_vocab(size)
    res = {"size": round(size), "level": level, "false_alarm": round(false_alarm * 100), "bands": detail}
    save(lang, "vocabulary", level, size, res)
    return res


def save(lang: str, skill: str, level: str, score: float, data: dict):
    db.execute("INSERT INTO assessments(lang, skill, level, score, data, ts) VALUES (?,?,?,?,?,?)",
               (lang, skill, level, score, json.dumps(data, ensure_ascii=False), db.now_iso()))


PROMPTS = {
    "speaking": {
        "A1": "Preséntate: nombre, de dónde eres, a qué te dedicas y qué te gusta hacer.",
        "A2": "Describe un día normal en tu vida y lo que hiciste el fin de semana pasado.",
        "B1": "Cuenta un viaje o experiencia que te marcó y explica por qué fue importante para ti.",
        "B2": "¿Es mejor trabajar desde casa o en una oficina? Da tu opinión con argumentos y ejemplos.",
        "C1": "Algunos dicen que la inteligencia artificial destruirá más empleos de los que creará. Analiza ambas posturas y concluye con tu opinión matizada.",
    },
    "writing": {
        "A1": "Escribe un mensaje corto a un amigo contándole dónde vives y qué haces (40-60 palabras).",
        "A2": "Escribe un correo a un amigo contándole tus últimas vacaciones (60-90 palabras).",
        "B1": "Escribe un correo a una empresa quejándote de un producto que compraste y pidiendo una solución (100-150 palabras).",
        "B2": "Escribe un ensayo: '¿Deberían las ciudades prohibir los coches en el centro?' Da argumentos a favor y en contra (150-220 palabras).",
        "C1": "Escribe un ensayo formal: 'La educación universitaria debería ser gratuita para todos.' Discute, evalúa y concluye (220-280 palabras).",
    },
}

RUBRIC = (
    "Use CEFR descriptors. Criteria (0-5 each, like Cambridge): "
    "range (variety of vocabulary and structures), accuracy (grammar and word choice), "
    "fluency_coherence (flow, linking, organisation), task (did they fully do the task, appropriate register). "
)


async def evaluate_speaking(lang: str, prompt: str, transcript: str, metrics: dict) -> dict:
    target = TARGET[lang]
    res = await llm.json_call(
        f"You are a certified {target} speaking examiner. Rate this monologue by a Spanish speaker (transcribed by speech recognition, so ignore punctuation). "
        + RUBRIC +
        "Also consider the objective metrics given (words per minute, long pauses, pronunciation score from a phoneme model). "
        "Return ONLY JSON {\"level\": \"A1|A2|B1|B2|C1|C2\", \"criteria\": {\"range\": 0-5, \"accuracy\": 0-5, \"fluency_coherence\": 0-5, \"task\": 0-5}, "
        "\"strengths\": [\"Spanish\"], \"to_reach_next_level\": [\"concrete advice in Spanish to reach the next CEFR level\"], "
        "\"corrections\": [{\"original\": \"phrase\", \"corrected\": \"fixed\", \"explanation\": \"Spanish\", \"category\": \"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|expresión natural|otro\"}], "
        "\"summary\": \"2-3 sentences in Spanish\"}",
        f"Task: {prompt}\nMetrics: {json.dumps(metrics)}\nTranscript: {transcript}",
        temperature=0.2, max_tokens=3000,
    )
    return _finish(lang, "speaking", res)


async def evaluate_writing(lang: str, prompt: str, text: str) -> dict:
    target = TARGET[lang]
    res = await llm.json_call(
        f"You are a certified {target} writing examiner. Rate this text by a Spanish speaker. " + RUBRIC +
        "Return ONLY JSON {\"level\": \"A1|A2|B1|B2|C1|C2\", \"criteria\": {\"range\": 0-5, \"accuracy\": 0-5, \"fluency_coherence\": 0-5, \"task\": 0-5}, "
        "\"strengths\": [\"Spanish\"], \"to_reach_next_level\": [\"concrete advice in Spanish\"], "
        "\"corrections\": [{\"original\": \"phrase (3-10 words)\", \"corrected\": \"fixed\", \"explanation\": \"Spanish\", \"category\": \"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|ortografía|expresión natural|otro\"}], "
        "\"improved\": \"the text rewritten at one CEFR level higher\", \"summary\": \"2-3 sentences in Spanish\"}",
        f"Task: {prompt}\nText:\n{text}",
        temperature=0.2, max_tokens=4000,
    )
    return _finish(lang, "writing", res)


def _finish(lang: str, skill: str, res: dict) -> dict:
    level = res.get("level") if res.get("level") in LEVELS else "A1"
    crit = res.get("criteria") or {}
    score = round(sum(float(v or 0) for v in crit.values()) / max(1, len(crit)) * 20, 1) if crit else 0
    for c in (res.get("corrections") or [])[:10]:
        db.log_mistake(lang, f"test_{skill}", c.get("original", ""), c.get("corrected", ""),
                       c.get("explanation", ""), c.get("category", "otro"))
    res["level"], res["score"] = level, score
    save(lang, skill, level, score, res)
    db.log_activity(lang, "assessment", xp=20, minutes=5, detail={"skill": skill, "level": level})
    return res


def record_comprehension(lang: str, skill: str, level: str, score: float):
    """Guarda un resultado de comprensión (Escucha o Lectura) para estimar ese nivel."""
    if skill in ("listening", "reading") and level in LEVELS:
        save(lang, f"{skill}_raw", level, score, {})


def _comprehension_level(lang: str, skill: str) -> dict | None:
    rows = db.query("SELECT level, score FROM assessments WHERE lang=? AND skill=? ORDER BY id DESC LIMIT 40",
                    (lang, f"{skill}_raw"))
    if not rows:
        return None
    best = None
    for lvl in LEVELS:
        scores = [r["score"] for r in rows if r["level"] == lvl][:4]
        if scores and sum(scores) / len(scores) >= 70:
            best = lvl
    return {"level": best or "pre-A1", "samples": len(rows)}


def summary(lang: str) -> dict:
    skills = {}
    for skill in ("vocabulary", "speaking", "writing"):
        hist = db.query("SELECT level, score, ts FROM assessments WHERE lang=? AND skill=? ORDER BY id DESC LIMIT 10",
                        (lang, skill))
        skills[skill] = {"level": hist[0]["level"], "score": hist[0]["score"], "date": hist[0]["ts"],
                         "history": hist[::-1]} if hist else None
        if skill == "vocabulary" and hist:
            skills[skill]["size"] = round(hist[0]["score"])
    for skill in ("listening", "reading"):
        skills[skill] = _comprehension_level(lang, skill)
    levels = [s["level"] for s in skills.values() if s and s.get("level") in LEVELS]
    overall = None
    # Con 1-2 destrezas medidas el "nivel global" engaña: se exige al menos 3.
    if len(levels) >= 3:
        idx = sorted(LEVELS.index(l) for l in levels)
        overall = LEVELS[idx[(len(idx) - 1) // 2]]  # mediana baja: no se infla por una sola destreza
    return {"skills": skills, "overall": overall, "target": "C1"}
