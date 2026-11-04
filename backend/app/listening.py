"""Escucha activa: diálogos y pódcasts generados a tu nivel, resumen oral/escrito y dictogloss.

- Escuchar a varios hablantes con acentos distintos y a velocidad natural es imprescindible
  para C1 (la mayoría de alumnos avanzados entienden texto pero no a nativos hablando).
- Resumir lo escuchado (output después del input) obliga a procesar el significado y
  a reutilizar el vocabulario nuevo.
- Dictogloss: escuchar un texto corto dos veces y reconstruirlo entrena la comprensión y la gramática.
"""
from __future__ import annotations

import json
import random

from . import db, llm
from .config import LANGUAGES, VOICE_GENDER

from .config import TARGET_NAMES as TARGET

LENGTH = {"A1": "8-10", "A2": "10-14", "B1": "14-18", "B2": "16-22", "C1": "18-26"}
STYLE = {
    "A1": "very simple, slow, short sentences, everyday words",
    "A2": "simple everyday language",
    "B1": "natural conversational language with some common expressions",
    "B2": "natural native speed with phrasal verbs, idioms and some fillers (well, you know)",
    "C1": "fully natural: idioms, colloquialisms, fillers, interruptions, humour, implicit meaning",
}

KINDS = {
    "dialogue": "a realistic conversation between 2 people in an everyday situation",
    "podcast": "an episode of a podcast where 2 hosts chat about the topic with opinions and anecdotes",
    "news": "a short radio news report with an anchor and a reporter on location",
    "interview": "a radio interview with an expert or an interesting person",
}


def _voice_for(lang: str, gender: str | None, used: set[str]) -> str:
    """Una voz del género pedido, con un acento distinto a los ya usados si es posible."""
    vs = LANGUAGES[lang]["voices"][:]
    random.shuffle(vs)
    g = (gender or "").lower()[:1]
    pool = [v for v in vs if VOICE_GENDER.get(v) == g and v not in used] or \
           [v for v in vs if v not in used] or vs
    return pool[0]


async def generate(lang: str, level: str, kind: str, topic: str | None) -> dict:
    target = TARGET[lang]
    res = await llm.json_call(
        f"You write {target} listening material for a Spanish-speaking learner at CEFR {level}. "
        f"Write {KINDS.get(kind, KINDS['dialogue'])}. Style: {STYLE.get(level, '')}. "
        f"Length: {LENGTH.get(level, '12')} lines. Make it interesting and realistic, with useful expressions. "
        "Return ONLY JSON {\"title\": \"...\", \"title_es\": \"...\", "
        "\"speakers\": [{\"name\": \"...\", \"gender\": \"f|m\"}] (2 speakers), "
        "\"lines\": [{\"speaker\": 0 or 1, \"t\": \"line in the target language\", \"es\": \"Spanish translation\"}], "
        "\"questions\": [{\"q\": \"comprehension question in the target language (include one about implicit meaning or attitude)\", \"options\": [3 options], \"answer\": index}] (4 questions), "
        "\"vocab\": [{\"t\": \"useful expression from the script\", \"es\": \"Spanish\"}] (6 items), "
        "\"summary\": \"3-sentence summary in the target language\"}",
        f"Topic: {topic or 'something interesting and realistic from daily life, work, travel, culture or technology'}",
        temperature=0.9, max_tokens=4000,
    )
    speakers = res.get("speakers") or [{"name": "A", "gender": "f"}, {"name": "B", "gender": "m"}]
    used: set[str] = set()
    for s in speakers:
        s["voice"] = _voice_for(lang, s.get("gender"), used)
        used.add(s["voice"])
    if not res.get("questions") and res.get("lines"):
        # A veces el modelo omite las preguntas: las pedimos aparte.
        try:
            script = "\n".join(str(l.get("t", "")) for l in res["lines"])
            q = await llm.json_call(
                f"Write 4 multiple-choice comprehension questions in {target} about this script (one about implicit meaning or attitude). "
                "Return ONLY JSON {\"questions\": [{\"q\": \"...\", \"options\": [3 options], \"answer\": index}]}",
                script, temperature=0.4, max_tokens=1200)
            res["questions"] = q.get("questions", [])
        except llm.LLMError:
            res["questions"] = []
    lines = [l for l in res.get("lines", []) if l.get("t")]
    for l in lines:
        try:
            l["speaker"] = int(l.get("speaker", 0)) % len(speakers)
        except (TypeError, ValueError):
            l["speaker"] = 0
    data = {**res, "speakers": speakers, "lines": lines, "kind": kind}
    lid = db.execute("INSERT INTO listenings(lang, level, kind, title, data, ts) VALUES (?,?,?,?,?,?)",
                     (lang, level, kind, res.get("title", "Escucha"), json.dumps(data, ensure_ascii=False), db.now_iso()))
    return {"id": lid, "level": level, **data}


def get(lid: int) -> dict | None:
    row = db.one("SELECT * FROM listenings WHERE id=?", (lid,))
    return {"id": row["id"], "level": row["level"], "done": row["done"], **json.loads(row["data"])} if row else None


async def evaluate_retell(lang: str, original: str, attempt: str, level: str, source: str) -> dict:
    """Corrige un resumen o reconstrucción: ideas cubiertas + errores de lengua."""
    target = TARGET[lang]
    res = await llm.json_call(
        f"You are a {target} teacher. A Spanish-speaking learner (CEFR {level}) listened to a text and wrote/said "
        f"their {'reconstruction (dictogloss)' if source == 'dictogloss' else 'summary'} of it. Evaluate it kindly but precisely. "
        "Return ONLY JSON {\"content_score\": 0-100 (how many key ideas were captured correctly), "
        "\"language_score\": 0-100 (grammar, vocabulary, naturalness), "
        "\"missed\": [\"key ideas they missed or misunderstood, in Spanish\"], "
        "\"corrections\": [{\"original\": \"wrong phrase (3-10 words)\", \"corrected\": \"fixed\", \"explanation\": \"short Spanish\", \"category\": \"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|ortografía|expresión natural|otro\"}], "
        "\"better\": \"an improved version of their text\", \"feedback\": \"2 sentences in Spanish\"}",
        f"Original text:\n{original}\n\nLearner's text:\n{attempt}",
        temperature=0.3, max_tokens=3000,
    )
    for c in (res.get("corrections") or [])[:8]:
        db.log_mistake(lang, source, c.get("original", ""), c.get("corrected", ""),
                       c.get("explanation", ""), c.get("category", "otro"))
    return res


async def dictogloss_text(lang: str, level: str, topic: str | None) -> dict:
    target = TARGET[lang]
    n = {"A1": 2, "A2": 3, "B1": 4, "B2": 4, "C1": 5}.get(level, 3)
    res = await llm.json_call(
        f"Write a short {target} text for a dictogloss exercise for a Spanish speaker at CEFR {level}: "
        f"{n} connected sentences, natural, with 1-2 target grammar structures typical of {level} and some useful collocations. "
        "Return ONLY JSON {\"text\": \"...\", \"es\": \"Spanish translation\", \"focus\": \"grammar/vocabulary focus in Spanish (short)\"}",
        f"Topic: {topic or 'a short anecdote, a piece of news, or an interesting fact'}",
        temperature=0.9, max_tokens=1200,
    )
    return res
