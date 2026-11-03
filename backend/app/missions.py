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

from . import content, db, llm
from .config import LANGUAGES

LEVEL_STYLE = {
    "A1": "Use very simple, short sentences (max 10 words), common words, speak slowly and clearly. Repeat or rephrase if the learner seems confused.",
    "A2": "Use simple sentences and everyday vocabulary. Rephrase when needed.",
    "B1": "Speak naturally but clearly, with some common expressions.",
    "B2": "Speak naturally at normal native speed, with idioms and phrasal verbs.",
    "C1": "Speak completely naturally, like with a native, including idioms and humour.",
}

EMOTIONS = ["neutral", "happy", "friendly", "confused", "suspicious", "annoyed", "impatient", "impressed"]


def _character_system(m: dict, lang: str, mode: str, objectives_state: dict) -> str:
    lname = LANGUAGES[lang]["name"]
    target = {"en": "English", "fr": "French"}[lang]
    ch = m["character"]
    objs = "\n".join(
        f'- {o["id"]}: {o["text"]} -> {"DONE" if objectives_state.get(o["id"]) else "pending"}'
        for o in m["objectives"]
    )
    profile = ""
    if m.get("free"):
        facts = db.get_setting("learner_profile", [])
        if facts:
            profile = "\n## What you remember about the learner from earlier chats (use it naturally, don't list it)\n- " + "\n- ".join(facts[-20:]) + "\n"
    extra = f"\n## Conversation format\n{m['format']}\n" if m.get("format") else ""
    return f"""You are role-playing in a language-immersion training game for a Spanish speaker learning {target}.
{profile}{extra}
## Your character
Name: {ch["name"]}. Role: {ch["role"]}. Personality: {ch["personality"]}.
Location: {m["location"]}.
What only you know / how you behave: {m.get("secret", "")}
Possible complication to introduce naturally after a few turns: {m.get("complication", "none")}

## Rules
- Stay 100% in character. Speak ONLY {target}. NEVER speak Spanish, never mention you are an AI or a teacher.
- If the learner writes in Spanish, react as a real {target} speaker would (confused, ask them to speak {target}).
- Do NOT volunteer the information the learner must obtain: they must ask for it.
- Replies: 1-3 short sentences, natural spoken language. {LEVEL_STYLE.get(m.get("level", "A2"), "")}
- Be realistic: if the learner is rude or unclear, react like a real person would.

## Learner's mission objectives (secret from the learner's perspective, you just track them)
{objs}
Mark an objective done only when the learner has clearly achieved it in {target} (minor grammar errors are OK if the meaning is clear).

## Output: ONLY JSON
{{
 "reply": "your in-character line in {target}",
 "emotion": one of {EMOTIONS},
 "objectives_done": ["ids of objectives completed so far, including earlier ones"],
 "correction": null OR {{"original": "the learner's exact wrong phrase", "corrected": "natural correct version", "hint": "a clue IN SPANISH that helps the learner find the error WITHOUT giving the answer (e.g. 'Revisa el tiempo verbal: es algo que ya pasó')", "explanation": "very short reason IN SPANISH", "category": "one of: tiempo verbal, preposición, artículo, orden de palabras, vocabulario, concordancia, pronombre, ortografía, expresión natural, otro"}},
 "mission_complete": true if ALL objectives are done and the scene reached a natural end,
 "mission_failed": true only if the learner clearly made it impossible (e.g. insulted you, left)
}}
Check the learner's LAST message carefully, like a strict teacher: wrong verb form or tense, missing/wrong article, wrong preposition (e.g. "for go" → "to go"), word order, false friends, or anything a native would never say. If there is any such error, you MUST fill "correction" (pick the most important one). Only use null if the message is truly correct and natural. Ignore missing punctuation/capitals (it comes from speech transcription)."""


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
    target = {"en": "English", "fr": "French"}[lang]
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


async def start_run(lang: str, mission: dict, mode: str) -> dict:
    opening = mission.get("opening") or ""
    if not opening:
        res = await llm.json_call(
            _character_system(mission, lang, mode, {}),
            "[The learner just arrived. Start the scene with a natural opening line. Return the JSON.]",
            temperature=0.8,
        )
        opening = res.get("reply", "Hi!")
    transcript = [{"role": "assistant", "content": opening, "emotion": "friendly"}]
    run_id = db.execute(
        "INSERT INTO mission_runs(lang, mission_id, mode, mission, transcript, state, started) VALUES (?,?,?,?,?,?,?)",
        (lang, mission["id"], mode, json.dumps(mission, ensure_ascii=False),
         json.dumps(transcript, ensure_ascii=False), json.dumps({"done": [], "corrections": []}), db.now_iso()),
    )
    return {"run_id": run_id, "mission": public_mission(mission), "opening": opening, "mode": mode}


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

    done_map = {d: True for d in state["done"]}
    messages = [{"role": "system", "content": _character_system(m, lang, run["mode"], done_map)}]
    for t in transcript[-16:]:
        messages.append({"role": t["role"], "content": t["content"]})
    res = await llm.chat(messages, json_mode=True, temperature=0.7, max_tokens=1200)

    reply = (res.get("reply") or "...").strip()
    valid_ids = {o["id"] for o in m["objectives"]}
    newly = [o for o in (res.get("objectives_done") or []) if o in valid_ids and o not in state["done"]]
    state["done"] = sorted(set(state["done"]) | set(newly))
    corr = res.get("correction")
    if isinstance(corr, dict) and corr.get("original") and corr.get("corrected") \
            and corr["original"].strip().lower() != corr["corrected"].strip().lower() \
            and _refers_to(corr["original"], text):
        state["corrections"].append(corr)
    else:
        corr = None
    user_turns = sum(1 for t in transcript if t["role"] == "user")
    complete = bool(res.get("mission_complete")) and len(state["done"]) == len(valid_ids)
    failed = bool(res.get("mission_failed"))
    out_of_turns = user_turns >= m.get("max_turns", 16)

    transcript.append({"role": "assistant", "content": reply, "emotion": res.get("emotion", "neutral")})
    db.execute("UPDATE mission_runs SET transcript=?, state=? WHERE id=?",
               (json.dumps(transcript, ensure_ascii=False), json.dumps(state, ensure_ascii=False), run_id))
    return {
        "reply": reply,
        "emotion": res.get("emotion", "neutral"),
        "objectives_done": state["done"],
        "new_objectives": newly,
        "correction": corr if run["mode"] == "entrenamiento" else None,
        "had_correction": corr is not None,
        "mission_complete": complete,
        "mission_failed": failed,
        "out_of_turns": out_of_turns and not complete,
        "turns_left": max(0, m.get("max_turns", 16) - user_turns),
    }


async def hint(run_id: int) -> dict:
    run = _load_run(run_id)
    m, lang = run["mission"], run["lang"]
    target = {"en": "English", "fr": "French"}[lang]
    pending = [o["text"] for o in m["objectives"] if o["id"] not in run["state"]["done"]]
    convo = "\n".join(f'{"Learner" if t["role"] == "user" else m["character"]["name"]}: {t["content"]}'
                      for t in run["transcript"][-8:])
    res = await llm.json_call(
        "You help a Spanish speaker in a role-play language game. Suggest what they could say NEXT. "
        f"Return JSON {{\"suggestions\": [{{\"t\": \"{target} phrase\", \"es\": \"Spanish translation\"}}], \"tip\": \"short tip in Spanish\"}} with 2-3 suggestions at CEFR {m.get('level','A2')}.",
        f"Pending objectives: {pending}\nConversation:\n{convo}",
        temperature=0.6, model=None,
    )
    return res


async def finish(run_id: int) -> dict:
    """Informe final (After Action Review): puntaje, errores, frases útiles."""
    run = _load_run(run_id)
    if run["finished"] and run["result"]:
        return json.loads(run["result"])
    m, lang, state = run["mission"], run["lang"], run["state"]
    target = {"en": "English", "fr": "French"}[lang]
    learner_lines = [t["content"] for t in run["transcript"] if t["role"] == "user"]
    convo = "\n".join(f'{"Learner" if t["role"] == "user" else m["character"]["name"]}: {t["content"]}'
                      for t in run["transcript"])
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
                "\"fluency\": 0-100, \"accuracy\": 0-100, "
                "\"profile_facts\": [\"short facts the Learner revealed about their REAL life (job, hobbies, family, goals, city), in English; empty list if none or if it was a role-play cover story\"]}",
                convo, temperature=0.4, max_tokens=2500,
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
    score = round(0.5 * obj_score + 0.3 * acc + 0.2 * flu, 1)
    success = done == objectives_total

    # Cada error se guarda en el cuaderno de errores y se convierte en tarjeta de repaso.
    source = "free_talk" if m.get("free") else "mission"
    for c in state["corrections"]:
        db.log_mistake(lang, source, c.get("original", ""), c.get("corrected", ""),
                       c.get("explanation", ""), c.get("category", "otro"))

    result = {
        "score": score, "success": success, "objectives_done": state["done"],
        "objectives_total": objectives_total, "corrections": state["corrections"],
        "turns": len(learner_lines), **{k: review.get(k) for k in
                                         ("summary", "strengths", "improvements", "better_versions", "new_vocab", "fluency", "accuracy")},
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
    target = {"en": "English", "fr": "French"}[lang]
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
