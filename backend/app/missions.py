"""Motor de MISIONES: juegos de rol con personajes en situaciones reales.

Inspirado en el entrenamiento por tareas (task-based) e inmersión que usan escuelas
militares de idiomas: recibes un informe (briefing), cumples la operación hablando solo
en el idioma meta con un personaje que tiene información que necesitas (vacío de
información), y al final hay un análisis posterior (After Action Review) con tus errores.

Modos:
  - entrenamiento: pistas, traducción de las frases del personaje y correcciones en vivo.
  - inmersion: sin ayudas; las correcciones se ven solo en el informe final.
"""
from __future__ import annotations

import json
import re
import uuid

from . import content, db, llm, scenes
from .config import LANGUAGES, TARGET_NAMES

LEVEL_STYLE = {
    "A1": "Use very simple, short sentences (max 10 words), common words, speak slowly and clearly. Repeat or rephrase if the learner seems confused.",
    "A2": "Use simple sentences and everyday vocabulary. Rephrase when needed.",
    "B1": "Speak naturally but clearly, with some common expressions.",
    "B2": "Speak naturally at normal native speed, with idioms and phrasal verbs.",
    "C1": "Speak completely naturally, like with a native, including idioms and humour.",
}

EMOTIONS = ["neutral", "happy", "friendly", "confused", "suspicious", "annoyed", "impatient", "impressed"]


def _character_system(m: dict, lang: str, mode: str, objectives_state: dict | None = None) -> str:
    """Instrucciones FIJAS del personaje (compactas: se envían en cada turno y cuentan tokens).
    Lo que cambia turno a turno va aparte, en _state_note()."""
    target = TARGET_NAMES[lang]
    ch = m["character"]
    objs = "; ".join(f'{o["id"]}={o["text"]}' for o in m["objectives"])
    profile = ""
    if m.get("free"):
        facts = db.get_setting("learner_profile", [])
        if facts:
            profile = "Learner facts (use naturally): " + "; ".join(facts[-12:]) + "\n"
    fmt = f"Format: {m['format']}\n" if m.get("format") else ""
    return f"""Role-play game: a Spanish speaker practises {target}. You are {ch["name"]}, {ch["role"]} ({ch["personality"]}) at {m["location"]}.
{profile}{fmt}Secret/behaviour: {m.get("secret", "")}
Complication (after a few turns): {m.get("complication", "none")}
Rules: stay in character; ONLY {target}, never Spanish, never say you are AI. If the learner uses Spanish, react confused. Don't volunteer what they must ask for. 1-3 short spoken sentences. {LEVEL_STYLE.get(m.get("level", "A2"), "")} Never stall or ask to wait twice: if blocked, say exactly what you need (e.g. "Could you spell your surname?") and resolve complications within 2 turns. If the learner seems confused, rephrase simply.
Learner objectives (track silently): {objs}. Mark one done only when clearly achieved (small errors OK).
Reply ONLY JSON: {{"reply":"{target} line","emotion":"neutral|happy|friendly|confused|suspicious|annoyed|impatient|impressed","objectives_done":["ids done so far"],"correction":null or {{"original":"learner's exact wrong phrase","corrected":"natural version","hint":"Spanish clue without the answer","explanation":"short Spanish reason","category":"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|expresión natural|otro"}},"mission_complete":bool,"mission_failed":bool}}
Correction: check the learner's LAST message like a strict teacher (tense, articles, prepositions, word order, unnatural phrasing); if there's an error you MUST fill it, else null. Ignore punctuation/capitals."""


BIG, SMALL = "openai/gpt-oss-120b", "openai/gpt-oss-20b"


def _turn_models(level: str) -> list[str]:
    """Modelo para los turnos del personaje. A1-B1: el pequeño basta (y ahorra el grande).
    B2-C1: el grande, mientras le quede cuota de sobra; si no, el que tenga más."""
    if level in ("B2", "C1", "C2") and llm.remaining(BIG) > 40_000:
        return [BIG, SMALL]
    if llm.remaining(SMALL) > 20_000:
        return [SMALL, BIG]
    return llm.route([BIG, SMALL])


def _state_note(m: dict, state: dict) -> str:
    """Nota breve con el estado actual (va al FINAL de los mensajes, no en las instrucciones)."""
    done = state.get("done", [])
    pending = [o["id"] for o in m["objectives"] if o["id"] not in done]
    note = f"[State: done={done or 'none'}; pending={pending or 'none'}."
    words = state.get("target_words") or []
    if words:
        used = set(state.get("words_used", []))
        left = [w["front"] for w in words if w["front"] not in used]
        if left:
            note += f" Naturally give the learner chances to use: {', '.join(left)}."
    stall = int(state.get("stall", 0))
    if stall >= 2 and not m.get("free"):
        note += (f" Scene stuck for {stall} turns: resolve the pending complication now or ask simply "
                 "for the one thing you need. Don't ask them to wait.")
    if state.get("variation"):
        note += f" This is a REPEAT with variation: {state['variation']}"
    return note + "]"


def _refers_to(fragment: str, message: str) -> bool:
    """¿La corrección habla del último mensaje? (a veces la IA repite una corrección anterior)."""
    from difflib import SequenceMatcher

    f = re.sub(r"[^\w' ]", "", fragment.lower()).strip()
    m = re.sub(r"[^\w' ]", "", message.lower()).strip()
    if not f:
        return False
    if f in m:
        return True
    match = SequenceMatcher(None, f, m).find_longest_match(0, len(f), 0, len(m))
    return match.size >= max(4, int(len(f) * 0.6))


def list_missions(lang: str) -> list[dict]:
    progress = {r["mission_id"]: r for r in db.query("SELECT * FROM mission_progress WHERE lang=?", (lang,))}
    last_run = {r["mission_id"]: r["f"] for r in db.query(
        "SELECT mission_id, MAX(finished) AS f FROM mission_runs WHERE lang=? AND finished IS NOT NULL GROUP BY mission_id", (lang,))}
    today = db.today()

    def repeat_due(mid: str, p) -> bool:
        # Repetir con variación 1-7 días después, mientras la marca sea mejorable.
        if not p or not p["completed"] or (p["best_score"] or 0) >= 90 or mid not in last_run:
            return False
        return last_run[mid][:10] < today and (p["runs"] or 0) < 4
    out = []
    for c in content.campaigns(lang):
        prev_done = True
        ms = []
        for m in c["missions"]:
            p = progress.get(m["id"])
            ms.append({
                "id": m["id"], "title": m["title"], "level": m["level"], "location": m["location"],
                "character": m["character"]["name"], "role": m["character"]["role"],
                "objectives": len(m["objectives"]),
                "best_score": p["best_score"] if p else None,
                "completed": bool(p and p["completed"]),
                "unlocked": prev_done,
                "repeat_due": repeat_due(m["id"], p),
            })
            prev_done = bool(p and p["completed"])
        out.append({"id": c["id"], "title": c["title"], "description": c["description"], "missions": ms})
    customs = db.query("SELECT id, data FROM custom_missions WHERE lang=? ORDER BY created DESC", (lang,))
    if customs:
        ms = []
        for row in customs:
            m = json.loads(row["data"])
            p = progress.get(m["id"])
            ms.append({"id": m["id"], "title": m["title"], "level": m["level"], "location": m["location"],
                       "character": m["character"]["name"], "role": m["character"]["role"],
                       "objectives": len(m["objectives"]),
                       "best_score": p["best_score"] if p else None,
                       "completed": bool(p and p["completed"]), "unlocked": True})
        out.append({"id": "custom", "title": "Misiones generadas", "description": "Misiones creadas por la IA a tu medida.", "missions": ms})
    return out


def get_mission(lang: str, mission_id: str) -> dict | None:
    m = content.mission(lang, mission_id)
    if m:
        return m
    row = db.one("SELECT data FROM custom_missions WHERE id=?", (mission_id,))
    return json.loads(row["data"]) if row else None


# Modos de conversación: cada uno entrena una destreza distinta (clave para llegar a C1).
CONVERSATION_MODES = {
    "libre": {
        "title": "Conversación libre", "icon": "💬", "desc": "Charla natural con un nativo curioso.",
        "role": "friendly native speaker and conversation partner",
        "personality": "curious, warm, asks follow-up questions, shares personal opinions and stories",
        "format": "Casual conversation. Always end with a question. Share your own opinions and experiences too.",
        "objectives": ["Mantén la conversación al menos 8 turnos", "Haz tú al menos 2 preguntas", "Cuenta algo personal con detalle"],
    },
    "debate": {
        "title": "Debate", "icon": "⚖️", "desc": "Defiende una postura con argumentos (destreza C1).",
        "role": "sharp but friendly debate partner",
        "personality": "logical, challenges every argument politely, asks for evidence and examples, plays devil's advocate",
        "format": "A debate. First state the motion and ask the learner which side they take. Then ALWAYS take the opposite side, counter their arguments and ask them to justify. Push for linkers (however, on the other hand) and concrete examples.",
        "objectives": ["Expón tu postura con claridad", "Da al menos 3 argumentos con ejemplos", "Rebate un argumento contrario", "Concluye resumiendo tu postura"],
    },
    "entrevista": {
        "title": "Entrevista de trabajo", "icon": "💼", "desc": "Prepárate para una entrevista real en el idioma.",
        "role": "experienced HR interviewer",
        "personality": "professional, friendly, asks behavioural questions and follow-ups (STAR method)",
        "format": "A realistic job interview for the job/topic given. Ask one question at a time: background, motivation, strengths, weakness, a difficult situation (STAR), salary expectations, questions for you. Ask follow-ups when answers are vague.",
        "objectives": ["Preséntate y resume tu experiencia", "Responde una pregunta de comportamiento con un ejemplo concreto", "Habla de una debilidad de forma profesional", "Haz tú una pregunta al entrevistador"],
    },
    "explicar": {
        "title": "Explícamelo (técnica Feynman)", "icon": "🧑‍🏫", "desc": "Explica un tema que conoces a alguien curioso.",
        "role": "curious friend who knows nothing about the topic",
        "personality": "curious, asks 'why?' and 'what do you mean by...?', asks for examples and simpler words",
        "format": "The learner explains the given topic to you. You know nothing about it. Ask clarifying questions, ask for examples, summarise what you understood and let them correct you.",
        "objectives": ["Explica qué es el tema", "Da un ejemplo concreto", "Aclara algo que no se entendió", "Responde a una pregunta de '¿por qué?'"],
    },
    "historia": {
        "title": "Cuéntame una historia", "icon": "📖", "desc": "Narra en pasado con detalle (tiempos verbales).",
        "role": "attentive listener who loves stories",
        "personality": "reacts with emotion, asks what happened next, how they felt, asks about details",
        "format": "The learner tells a real or invented story about the given topic. React naturally, ask what happened next, about feelings and details. Encourage past tenses and storytelling linkers (then, suddenly, eventually).",
        "objectives": ["Sitúa la historia (cuándo, dónde, quién)", "Cuenta lo que pasó usando tiempos del pasado", "Describe cómo te sentiste", "Cuenta cómo terminó"],
    },
    "actualidad": {
        "title": "Actualidad y opinión", "icon": "📰", "desc": "Opina sobre temas sociales con matices.",
        "role": "well-informed friend who follows the news",
        "personality": "thoughtful, nuanced, asks for opinions and reasons, brings up pros and cons",
        "format": "Discuss the given social topic (technology, environment, work, education, cities...). Ask for opinions, reasons, personal impact, and possible solutions. Use and encourage nuanced language (to some extent, it depends).",
        "objectives": ["Da tu opinión con razones", "Matiza tu opinión (depende, en parte...)", "Propón una solución o predicción", "Pregunta la opinión del otro"],
    },
    "smalltalk": {
        "title": "Small talk", "icon": "☕", "desc": "Charla ligera como en una fiesta o una oficina.",
        "role": "friendly stranger at a social event",
        "personality": "relaxed, polite, light topics: weather, weekend, travel, food, work in general",
        "format": "Light small talk between people who just met. Keep it short and natural, with typical small-talk phrases. Change topic naturally a couple of times.",
        "objectives": ["Preséntate de forma natural", "Encuentra algo en común", "Cambia de tema con naturalidad", "Despídete de forma natural"],
    },
}


def free_talk_mission(lang: str, topic: str, level: str, kind: str = "libre") -> dict:
    target = TARGET_NAMES[lang]
    voices = LANGUAGES[lang]["voices"]
    mode = CONVERSATION_MODES.get(kind, CONVERSATION_MODES["libre"])
    import random as _r
    from .config import VOICE_GENDER
    voice = _r.choice(voices)
    names = {
        ("en", "f"): ["Emma", "Olivia", "Sophie", "Grace"], ("en", "m"): ["James", "Tom", "Daniel", "Ben"],
        ("fr", "f"): ["Manon", "Léa", "Chloé", "Camille"], ("fr", "m"): ["Lucas", "Hugo", "Julien", "Antoine"],
    }[(lang, VOICE_GENDER.get(voice, "f"))]
    n_turns = 8
    return {
        "id": f"free-{kind}-{uuid.uuid4().hex[:6]}",
        "level": level,
        "title": mode["title"],
        "location": "Conversación",
        "briefing": f"{mode['desc']} Tema: {topic}.",
        "character": {"name": _r.choice(names), "role": f"{mode['role']} (native {target} speaker)",
                      "personality": mode["personality"], "voice": voice},
        "objectives": [{"id": f"o{i+1}", "text": t} for i, t in enumerate(mode["objectives"])],
        "secret": f"Topic: {topic}. Objective 'o1' in the free mode is done after the learner's {n_turns}th message.",
        "format": mode["format"],
        "complication": "Bring a surprising opinion or question to make the learner react.",
        "opening": "",
        "useful_phrases": [],
        "max_turns": 30,
        "free": True,
        "kind": kind,
    }


async def ensure_scene(lang: str, mission: dict) -> dict | None:
    """Devuelve la escena preparada de la misión; si no existe, la genera UNA vez y la guarda."""
    if mission.get("free"):
        return None
    sc = scenes.get_scene(lang, mission)
    if sc:
        return sc
    sc = await scenes.generate_scene(lang, mission)
    row = db.one("SELECT data FROM custom_missions WHERE id=?", (mission["id"],))
    if row:  # misión generada por IA: la escena se guarda junto a ella
        data = json.loads(row["data"])
        data["scene"] = sc
        db.execute("UPDATE custom_missions SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), mission["id"]))
    else:
        scenes.save_scene(lang, mission["id"], sc)
    return sc


async def start_run(lang: str, mission: dict, mode: str, variation: str | None = None,
                    engine: str = "llm") -> dict:
    opening = mission.get("opening") or ""
    if not opening:
        res = await llm.json_call(
            _character_system(mission, lang, mode, {}),
            "[The learner just arrived. Start the scene with a natural opening line. Return the JSON.]",
            temperature=0.8, max_tokens=500, models=[SMALL, BIG],
        )
        opening = res.get("reply", "Hi!")
    transcript = [{"role": "assistant", "content": opening, "emotion": "friendly"}]
    state = {"done": [], "corrections": [], "target_words": pick_target_words(lang), "words_used": []}
    if variation:
        state["variation"] = variation
    # En una repetición con variación la escena preparada no encaja (cambian los datos): se usa IA.
    if engine == "scene" and not variation:
        try:
            if await ensure_scene(lang, mission):
                state["engine"] = "scene"
        except (llm.LLMError, ValueError) as e:
            import logging
            logging.getLogger("missions").warning("No se pudo preparar la escena: %s", e)
    run_id = db.execute(
        "INSERT INTO mission_runs(lang, mission_id, mode, mission, transcript, state, started) VALUES (?,?,?,?,?,?,?)",
        (lang, mission["id"], mode, json.dumps(mission, ensure_ascii=False),
         json.dumps(transcript, ensure_ascii=False), json.dumps(state, ensure_ascii=False), db.now_iso()),
    )
    return {"run_id": run_id, "mission": public_mission(mission), "opening": opening, "mode": mode,
            "target_words": state["target_words"], "engine": state.get("engine", "llm")}


FUNCTION_WORDS = {"have", "with", "that", "this", "from", "they", "there", "their", "would", "could", "should", "about",
                  "what", "when", "your", "were", "been", "will", "into", "than", "then", "them", "some", "just",
                  "also", "only", "very", "much", "more", "most", "such", "even", "over", "like", "does", "doing"}


def pick_target_words(lang: str, n: int = 4) -> list[dict]:
    """Palabras/expresiones de TU repaso para usar en la misión (las más urgentes primero).
    Usarlas al hablar suma los encuentros que hacen falta para dominarlas de forma productiva."""
    rows = db.query(
        "SELECT id, front, back, kind, extra FROM cards WHERE lang=? AND suspended=0 AND kind IN ('word','phrase') "
        "AND state IN (1,2,3) AND length(front) > 3 ORDER BY due LIMIT ?", (lang, n * 10))
    function_pos = {"det", "pron", "prep", "conj", "aux", "num", "interj", "other"}

    def useful(r) -> bool:
        if r["front"].strip().lower() == r["back"].strip().lower():
            return False  # tarjeta mal guardada (misma palabra en ambas caras)
        if r["kind"] == "phrase":
            return True
        pos = (json.loads(r["extra"] or "{}").get("pos") or "").lower()
        return pos not in function_pos and r["front"].lower() not in FUNCTION_WORDS
    import random as _r
    rows = [r for r in rows if useful(r)][: n * 2]
    if len(rows) < n:  # pocas en repaso: completamos con tarjetas nuevas útiles de tu mazo
        extra = db.query(
            "SELECT id, front, back, kind, extra FROM cards WHERE lang=? AND suspended=0 AND kind IN ('word','phrase') "
            "AND state=0 AND length(front) > 3 ORDER BY created LIMIT ?", (lang, n * 10))
        rows += [r for r in extra if useful(r)][: n - len(rows)]
    _r.shuffle(rows)
    return [{"id": r["id"], "front": r["front"], "back": r["back"]} for r in rows[:n]]


def public_mission(m: dict) -> dict:
    """Lo que ve el jugador (sin la información secreta del personaje)."""
    return {k: m[k] for k in ("id", "level", "title", "location", "briefing", "objectives", "useful_phrases", "max_turns")
            if k in m} | {"character": {k: m["character"][k] for k in ("name", "role", "voice")}, "free": m.get("free", False)}


def _load_run(run_id: int) -> dict:
    row = db.one("SELECT * FROM mission_runs WHERE id=?", (run_id,))
    if not row:
        raise KeyError(run_id)
    row["mission"] = json.loads(row["mission"])
    row["transcript"] = json.loads(row["transcript"])
    row["state"] = json.loads(row["state"])
    return row


async def turn(run_id: int, text: str) -> dict:
    run = _load_run(run_id)
    if run["finished"]:
        raise ValueError("La misión ya terminó")
    m, lang, state = run["mission"], run["lang"], run["state"]
    transcript = run["transcript"]
    transcript.append({"role": "user", "content": text})
    valid_ids = {o["id"] for o in m["objectives"]}
    stall = int(state.get("stall", 0))
    user_turns = sum(1 for t in transcript if t["role"] == "user")

    # Palabras de tu repaso que usaste en este mensaje (sin IA: búsqueda de texto).
    low = " " + re.sub(r"[^\w' ]", " ", text.lower()) + " "
    for w in state.get("target_words") or []:
        key = re.sub(r"^(der|die|das|to|the|a|an|le|la|les|o|os|as) ", "", w["front"].lower()).strip()
        if key and f" {key} " in low and w["front"] not in state.setdefault("words_used", []):
            state["words_used"].append(w["front"])

    reply, emotion, newly, corr, complete, failed, engine_used = None, "neutral", [], None, False, False, "llm"

    # 1) Modo escena: el enrutador local intenta responder SIN IA.
    if state.get("engine") == "scene":
        from fastapi.concurrency import run_in_threadpool
        scene = scenes.get_scene(lang, m)
        if scene:
            move, _sim = await run_in_threadpool(scenes.route, scene, state, text)
            if move:
                engine_used = "scene"
                state.setdefault("moves_done", []).append(move["id"])
                if move["objective"] and move["objective"] not in state["done"]:
                    newly = [move["objective"]]
                reply, emotion = move["reply"], "friendly"
                state["scene_misses"] = 0
            else:
                state["scene_misses"] = int(state.get("scene_misses", 0)) + 1
                ai_ok = state.get("allow_ai", True) and (llm.remaining(SMALL) + llm.remaining(BIG)) > 8000
                if not ai_ok:
                    engine_used = "scene"
                    reply, emotion = scenes.nudge_line(scene, m, state), "confused"

    # 2) Turno de IA (instrucciones compactas + saludo inicial + últimos 6 mensajes + nota de estado).
    if reply is None:
        messages = [{"role": "system", "content": _character_system(m, lang, run["mode"])}]
        hist = transcript if len(transcript) <= 7 else transcript[:1] + transcript[-6:]
        for t in hist:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "system", "content": _state_note(m, state)})
        res = await llm.chat(messages, json_mode=True, temperature=0.7, max_tokens=700,
                             models=_turn_models(m.get("level", "A2")))
        reply = (res.get("reply") or "...").strip()
        emotion = res.get("emotion", "neutral")
        newly = [o for o in (res.get("objectives_done") or []) if o in valid_ids and o not in state["done"]]
        failed = bool(res.get("mission_failed"))
        corr = res.get("correction")
        if isinstance(corr, dict) and corr.get("original") and corr.get("corrected") \
                and corr["original"].strip().lower() != corr["corrected"].strip().lower() \
                and _refers_to(corr["original"], text):
            state["corrections"].append(corr)
        else:
            corr = None
        complete = bool(res.get("mission_complete"))

    state["done"] = sorted(set(state["done"]) | set(newly))
    state["stall"] = 0 if newly else stall + 1
    all_done = len(state["done"]) == len(valid_ids)
    if engine_used == "scene" and all_done:
        complete = True
        closing = (scenes.get_scene(lang, m) or {}).get("closing")
        if closing and closing not in reply and not state.get("closed"):
            reply = f"{reply} {closing}"
        state["closed"] = True
    complete = complete and all_done
    out_of_turns = user_turns >= m.get("max_turns", 16)
    state.setdefault("engine_log", []).append(engine_used)

    transcript.append({"role": "assistant", "content": reply, "emotion": emotion})
    db.execute("UPDATE mission_runs SET transcript=?, state=? WHERE id=?",
               (json.dumps(transcript, ensure_ascii=False), json.dumps(state, ensure_ascii=False), run_id))
    return {
        "reply": reply,
        "emotion": emotion,
        "objectives_done": state["done"],
        "new_objectives": newly,
        "correction": corr if run["mode"] == "entrenamiento" else None,
        "had_correction": corr is not None,
        "mission_complete": complete,
        "mission_failed": failed,
        "out_of_turns": out_of_turns and not complete,
        "turns_left": max(0, m.get("max_turns", 16) - user_turns),
        "stuck": state["stall"] >= 3 and not m.get("free"),  # el frontend ofrece una pista
        "words_used": state.get("words_used", []),
        "engine": engine_used,  # "scene" = respondido sin gastar IA
    }


async def hint(run_id: int) -> dict:
    run = _load_run(run_id)
    m, lang = run["mission"], run["lang"]
    target = TARGET_NAMES[lang]
    pending = [o["text"] for o in m["objectives"] if o["id"] not in run["state"]["done"]]
    convo = "\n".join(f'{"Learner" if t["role"] == "user" else m["character"]["name"]}: {t["content"]}'
                      for t in run["transcript"][-8:])
    res = await llm.json_call(
        "You help a Spanish speaker in a role-play language game. Suggest what they could say NEXT. "
        f"Return JSON {{\"suggestions\": [{{\"t\": \"{target} phrase\", \"es\": \"Spanish translation\"}}], \"tip\": \"short tip in Spanish\"}} with 2-3 suggestions at CEFR {m.get('level','A2')}.",
        f"Pending objectives: {pending}\nConversation:\n{convo}",
        temperature=0.6, max_tokens=700, models=[SMALL, BIG],
    )
    return res


async def finish(run_id: int) -> dict:
    """Informe final (After Action Review): puntaje, errores, frases útiles."""
    run = _load_run(run_id)
    if run["finished"] and run["result"]:
        return json.loads(run["result"])
    m, lang, state = run["mission"], run["lang"], run["state"]
    target = TARGET_NAMES[lang]
    learner_lines = [t["content"] for t in run["transcript"] if t["role"] == "user"]
    # Ahorro: el informe recibe la situación y SOLO las frases del alumno (no todo el diálogo).
    convo = (f"Situation: {m.get('title')} — {m.get('location')}. The learner talked with {m['character']['name']} "
             f"({m['character']['role']}).\nLearner lines:\n" + "\n".join(f"{i + 1}. {l}" for i, l in enumerate(learner_lines)))
    objectives_total = len(m["objectives"])
    done = len(state["done"])

    review = {"summary": "", "strengths": [], "improvements": [], "better_versions": [], "new_vocab": [], "fluency": 0, "accuracy": 0}
    if learner_lines and llm.available():
        try:
            review = await llm.json_call(
                f"You are a {target} teacher writing an After Action Review (in Spanish) of a role-play mission done by a Spanish speaker at CEFR {m.get('level')}. "
                "Return ONLY JSON: {\"summary\": \"2-3 sentences in Spanish\", \"strengths\": [\"...\"], "
                "\"improvements\": [\"concrete advice in Spanish\"], "
                f"\"better_versions\": [{{\"original\": \"exact line said by the Learner (never the character)\", \"better\": \"more natural {target}\", \"why\": \"Spanish\"}}] (max 4, only Learner lines worth improving), "
                f"\"new_vocab\": [{{\"t\": \"useful {target} word or phrase from this situation\", \"es\": \"Spanish\"}}] (5 items), "
                f"\"errors\": [{{\"original\": \"wrong phrase copied from a Learner line\", \"corrected\": \"natural {target}\", \"explanation\": \"short Spanish\", \"category\": \"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|expresión natural|otro\"}}] (max 6, real errors only), "
                "\"fluency\": 0-100, \"accuracy\": 0-100, "
                "\"profile_facts\": [\"short facts the Learner revealed about their REAL life (job, hobbies, family, goals, city), in English; empty list if none or if it was a role-play cover story\"]}",
                convo, temperature=0.4, max_tokens=1800, models=[BIG, SMALL], fallbacks=False,
            )
        except llm.LLMError:
            pass
    # Memoria: lo que el alumno contó de sí mismo en conversaciones libres (personaliza futuras charlas).
    if m.get("free"):
        facts = [f for f in (review.get("profile_facts") or []) if isinstance(f, str) and 3 < len(f) < 120]
        if facts:
            known = db.get_setting("learner_profile", [])
            known += [f for f in facts if f.lower() not in {k.lower() for k in known}]
            db.set_setting("learner_profile", known[-30:])
    # Solo se "mejoran" frases que dijo el alumno (a veces la IA incluye líneas del personaje).
    low = [l.lower().strip() for l in learner_lines]
    review["better_versions"] = [
        b for b in (review.get("better_versions") or [])
        if isinstance(b, dict) and any(
            (b.get("original") or "").lower().strip(" .!?") in l or l.strip(" .!?") in (b.get("original") or "").lower()
            for l in low)
    ]

    obj_score = 100 * done / objectives_total if objectives_total else 0
    acc = float(review.get("accuracy") or 0)
    flu = float(review.get("fluency") or 0)
    if review.get("accuracy") is None and review.get("fluency") is None or (not acc and not flu and not review.get("summary")):
        # El análisis no se pudo generar (sin cuota): no se penaliza, cuentan solo los objetivos.
        score = round(obj_score, 1)
        review["summary"] = review.get("summary") or ("No se pudo generar el análisis detallado (cuota de IA agotada "
                                                      "por ahora); tu puntuación se basa en los objetivos cumplidos.")
    else:
        score = round(0.5 * obj_score + 0.3 * acc + 0.2 * flu, 1)
    success = done == objectives_total

    # Errores detectados en el informe (clave en modo escena, donde no hay corrección turno a turno).
    seen_orig = {c.get("original", "").strip().lower() for c in state["corrections"]}
    for e in review.get("errors") or []:
        if isinstance(e, dict) and e.get("original") and e.get("corrected") \
                and e["original"].strip().lower() not in seen_orig \
                and e["original"].strip().lower() != e["corrected"].strip().lower() \
                and any(_refers_to(e["original"], l) for l in learner_lines):
            state["corrections"].append(e)
            seen_orig.add(e["original"].strip().lower())

    # Cada error se guarda en el cuaderno de errores y se convierte en tarjeta de repaso.
    source = "free_talk" if m.get("free") else "mission"
    for c in state["corrections"]:
        db.log_mistake(lang, source, c.get("original", ""), c.get("corrected", ""),
                       c.get("explanation", ""), c.get("category", "otro"))

    # Palabras de tu repaso que USASTE hablando: cuentan como repaso acertado si tocaba repasarlas.
    from . import srs
    used = state.get("words_used", [])
    credited = []
    for w in state.get("target_words") or []:
        if w["front"] in used:
            row = db.one("SELECT due FROM cards WHERE id=?", (w["id"],))
            if row and row["due"] <= db.now_iso():
                try:
                    srs.review(w["id"], "good")
                    credited.append(w["front"])
                except KeyError:
                    pass

    # Repetición de tarea: comparación con tu intento anterior de la misma misión.
    prev_run = db.one("SELECT result FROM mission_runs WHERE lang=? AND mission_id=? AND finished IS NOT NULL "
                      "AND id<? ORDER BY id DESC LIMIT 1", (lang, m["id"], run_id)) if not m.get("free") else None
    prev_score = None
    if prev_run and prev_run["result"]:
        pr = json.loads(prev_run["result"])
        if not pr.get("abandoned"):
            prev_score = pr.get("score")

    result = {
        "score": score, "success": success, "objectives_done": state["done"],
        "objectives_total": objectives_total, "corrections": state["corrections"],
        "turns": len(learner_lines), **{k: review.get(k) for k in
                                         ("summary", "strengths", "improvements", "better_versions", "new_vocab", "fluency", "accuracy")},
        "target_words": [w["front"] for w in state.get("target_words") or []],
        "words_used": used, "words_credited": credited,
        "previous_score": prev_score,
        "scene_turns": (state.get("engine_log") or []).count("scene"),
        "ai_turns": (state.get("engine_log") or []).count("llm"),
        "repeat": bool(state.get("variation")),
    }
    db.execute("UPDATE mission_runs SET result=?, finished=? WHERE id=?",
               (json.dumps(result, ensure_ascii=False), db.now_iso(), run_id))
    if not m.get("free"):
        prev = db.one("SELECT * FROM mission_progress WHERE lang=? AND mission_id=?", (lang, m["id"]))
        best = max(score, prev["best_score"]) if prev else score
        completed = (prev and prev["completed"]) or (db.now_iso() if success else None)
        db.execute(
            "INSERT INTO mission_progress(lang, mission_id, best_score, runs, completed) VALUES (?,?,?,?,?) "
            "ON CONFLICT(lang, mission_id) DO UPDATE SET best_score=?, runs=runs+1, completed=?",
            (lang, m["id"], best, 1, completed, best, completed),
        )
    xp = int(10 + score / 5 + (20 if success else 0))
    minutes = max(1.0, len(learner_lines) * 0.6)
    db.log_activity(lang, "free_talk" if m.get("free") else "mission", xp, minutes,
                    {"mission": m["id"], "score": score, "success": success})
    result["xp"] = xp
    return result


async def generate_mission(lang: str, level: str, theme: str | None) -> dict:
    """La IA crea una misión nueva a tu nivel (se guarda para repetirla)."""
    target = TARGET_NAMES[lang]
    voices = LANGUAGES[lang]["voices"]
    res = await llm.json_call(
        f"You design realistic role-play missions for Spanish speakers learning {target} (task-based learning, like military language immersion). "
        "The learner must obtain information or achieve a goal by talking to a character who holds that information (information gap). "
        f"The scene MUST take place in a country where {target} is spoken (never in a Spanish-speaking country), and the character only speaks {target}. "
        "Return ONLY JSON with keys: title (Spanish), location (Spanish), briefing (Spanish, 2-3 sentences, mission style, includes any facts the learner needs like their name/budget), "
        f"character {{name, role (English), personality (English), voice (one of {voices})}}, "
        "objectives [{id: o1..o4, text (Spanish)}] (3-4 objectives), "
        "secret (English: facts the character knows, when to reveal them, how to behave), complication (English), "
        f"opening (character's first line in {target}), useful_phrases [{{t: {target}, es: Spanish}}] (4), max_turns (12-20).",
        f"CEFR level: {level}. Theme: {theme or 'any realistic everyday or travel or work situation, surprising and fun'}.",
        temperature=0.9, max_tokens=2500,
    )
    m = {
        "id": f"custom-{uuid.uuid4().hex[:8]}",
        "level": level,
        "title": res.get("title", "Misión"),
        "location": res.get("location", ""),
        "briefing": res.get("briefing", ""),
        "character": {"name": res.get("character", {}).get("name", "Alex"),
                      "role": res.get("character", {}).get("role", "local"),
                      "personality": res.get("character", {}).get("personality", "friendly"),
                      "voice": res.get("character", {}).get("voice") if res.get("character", {}).get("voice") in voices else voices[0]},
        "objectives": [{"id": o.get("id", f"o{i+1}"), "text": o.get("text", "")} for i, o in enumerate(res.get("objectives", [])[:4])],
        "secret": res.get("secret", ""),
        "complication": res.get("complication", ""),
        "opening": res.get("opening", ""),
        "useful_phrases": res.get("useful_phrases", [])[:5],
        "max_turns": int(res.get("max_turns") or 16),
    }
    db.execute("INSERT INTO custom_missions(id, lang, data, created) VALUES (?,?,?,?)",
               (m["id"], lang, json.dumps(m, ensure_ascii=False), db.now_iso()))
    return m
