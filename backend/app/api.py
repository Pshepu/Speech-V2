"""Rutas de la API (/api/...)."""
from __future__ import annotations

import json
import random
import re
from difflib import SequenceMatcher

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel

from . import assessment, audio, config, content, db, g2p, listening, llm, missions, planner, pronunciation, srs, stt, tts

router = APIRouter(prefix="/api")
TARGET = config.TARGET_NAMES


def L(lang: str | None) -> str:
    return content.check_lang(lang or db.get_setting("lang", "en"))


def _llm_error(e: Exception):
    raise HTTPException(503, f"IA no disponible: {e}")


# =====================================================================
# General
# =====================================================================

@router.get("/meta")
def meta(lang: str | None = None):
    lang = L(lang)
    return {
        "languages": [{k: v[k] for k in ("code", "name", "flag", "voices")} for v in config.LANGUAGES.values()],
        "levels": config.LEVELS,
        "settings": {
            "lang": db.get_setting("lang", "en"),
            "level": db.get_setting(f"level_{lang}", "A1"),
            "daily_minutes": db.get_setting("daily_minutes", 20),
            "new_cards_per_day": db.get_setting("new_cards_per_day", 15),
            "speech_rate": db.get_setting("speech_rate", 0),
            "onboarded": db.get_setting("onboarded", False),
        },
        "ai": llm.available(),
        "phoneme_engine": pronunciation.status(),
        "content": {
            "vocab": len(content.vocab(lang)), "sentences": len(content.sentences(lang)),
            "lessons": len(content.grammar(lang)),
            "missions": sum(len(c["missions"]) for c in content.campaigns(lang)),
        },
    }


class SettingsIn(BaseModel):
    lang: str | None = None
    level: str | None = None
    daily_minutes: int | None = None
    new_cards_per_day: int | None = None
    speech_rate: int | None = None
    onboarded: bool | None = None


@router.put("/settings")
def put_settings(s: SettingsIn):
    if s.lang:
        db.set_setting("lang", content.check_lang(s.lang))
    lang = L(None)
    if s.level and s.level in config.LEVELS:
        db.set_setting(f"level_{lang}", s.level)
    for k in ("daily_minutes", "new_cards_per_day", "speech_rate", "onboarded"):
        v = getattr(s, k)
        if v is not None:
            db.set_setting(k, v)
    return meta(lang)


@router.get("/plan")
def plan(lang: str | None = None):
    return planner.daily_plan(L(lang))


@router.get("/stats")
def stats(lang: str | None = None):
    return planner.stats(L(lang))


class TTSIn(BaseModel):
    text: str
    lang: str = "en"
    voice: str | None = None
    rate: int = 0
    random_voice: bool = False


@router.post("/tts")
async def tts_route(req: TTSIn):
    text = req.text.strip()[:1500]
    if not text:
        raise HTTPException(400, "texto vacío")
    try:
        data, voice = await tts.synthesize(text, L(req.lang), req.voice, req.rate, req.random_voice)
    except Exception as e:
        raise HTTPException(503, f"No se pudo generar el audio (¿hay internet?): {e}")
    return Response(data, media_type="audio/mpeg", headers={"X-Voice": voice, "Cache-Control": "max-age=86400"})


@router.post("/stt")
async def stt_route(audio_file: UploadFile = File(..., alias="audio"), lang: str = Form("en"), prompt: str = Form("")):
    data = await audio_file.read()
    try:
        return await stt.transcribe(data, L(lang), prompt or None)
    except llm.LLMError as e:
        _llm_error(e)


class TranslateIn(BaseModel):
    text: str
    lang: str = "en"
    context: str | None = None


@router.post("/translate")
async def translate(req: TranslateIn):
    lang, text = L(req.lang), req.text.strip()[:600]
    key = text if not req.context else f"{text}||{req.context[:200]}"
    cached = db.one("SELECT result FROM translations WHERE lang=? AND text=?", (lang, key))
    if cached:
        return json.loads(cached["result"])
    try:
        res = await llm.json_call(
            f"Translate from {TARGET[lang]} to Spanish. Return ONLY JSON "
            "{\"translation\": \"natural Spanish\", \"lemma\": \"dictionary form if single word else null\", "
            "\"note\": \"very short grammar/usage note in Spanish or null\"}",
            text if not req.context else f"Text: {text}\nContext sentence: {req.context}",
            model=config.LLM_FAST_MODEL, temperature=0.2, max_tokens=600,
        )
    except llm.LLMError as e:
        _llm_error(e)
    db.execute("INSERT OR REPLACE INTO translations(lang, text, result) VALUES (?,?,?)",
               (lang, key, json.dumps(res, ensure_ascii=False)))
    return res


# =====================================================================
# Pronunciación
# =====================================================================

@router.get("/practice/sentence")
def practice_sentence(lang: str | None = None, level: str | None = None, phoneme: str | None = None):
    lang = L(lang)
    level = level or db.get_setting(f"level_{lang}", "A1")
    s = None
    if phoneme:
        s = _sentence_with_phoneme(lang, level, phoneme)
    s = s or content.random_sentence(lang, level)
    if not s:
        # Mientras se genera el contenido de un idioma nuevo, usamos las frases útiles de sus misiones.
        phrases = [{"text": p["t"], "translation": p["es"], "level": m.get("level", "A1")}
                   for c in content.campaigns(lang) for m in c["missions"] for p in m.get("useful_phrases", [])]
        s = random.choice(phrases) if phrases else {"text": "Hello, how are you?", "translation": "Hola, ¿cómo estás?", "level": "A1"}
    words = [{"word": w, "ipa": ipa} for w, ipa in g2p.display_ipa_words(s["text"], lang)]
    return {**s, "words": words, "ipa": " ".join(w["ipa"] for w in words)}


def _sentence_with_phoneme(lang: str, level: str, phoneme: str) -> dict | None:
    levels = config.LEVELS
    idx = levels.index(level) if level in levels else 0
    pool = [s for s in content.sentences(lang) if s["level"] in levels[max(0, idx - 1): idx + 1]]
    random.shuffle(pool)
    for s in pool[:150]:
        phones = [p for _, ps in g2p.sentence_phones(s["text"], lang) for p in ps]
        if phones.count(phoneme) >= 2 or (phoneme in phones and len(phones) < 20):
            return s
    return None


@router.post("/practice/assess")
async def practice_assess(audio_file: UploadFile = File(..., alias="audio"), text: str = Form(...),
                          lang: str = Form("en"), mode: str = Form("practice"), transcribe: str = Form("1")):
    lang = L(lang)
    data = await audio_file.read()
    try:
        x, _ = audio.wav_to_float(data)
    except Exception:
        raise HTTPException(400, "Audio no válido")
    x = audio.trim_silence(x)
    if audio.duration(x) < 0.3:
        raise HTTPException(422, "No se oyó nada. Revisa el micrófono y habla más cerca.")

    result = None
    if pronunciation.load():
        try:
            result = await run_in_threadpool(pronunciation.assess, x, text, lang)
        except ValueError as e:
            raise HTTPException(422, str(e))
    if result is None:
        result = await _assess_fallback(data, text, lang)

    # Transcripción con Whisper (opcional) para mostrar qué se entendió.
    if transcribe != "0" and llm.available() and result["engine"] == "phoneme":
        try:
            tr = await stt.transcribe(data, lang)
            result["transcript"] = tr["text"]
        except Exception:
            result["transcript"] = None

    _record_pron(lang, text, result, mode)
    return result


async def _assess_fallback(data: bytes, text: str, lang: str) -> dict:
    """Sin modelo de fonemas: compara palabra a palabra con la transcripción de Whisper."""
    try:
        tr = await stt.transcribe(data, lang)
    except llm.LLMError as e:
        raise HTTPException(503, f"Sin motor de fonemas ni Whisper disponible: {e}")
    norm = lambda w: re.sub(r"[^\w']", "", w.lower())
    exp = g2p.words_of(text)
    got = [norm(w["text"]) for w in tr["words"]] or [norm(w) for w in tr["text"].split()]
    sm = SequenceMatcher(a=[norm(w) for w in exp], b=got)
    ok = set()
    for blk in sm.get_matching_blocks():
        ok.update(range(blk.a, blk.a + blk.size))
    words = [{"word": w, "ipa": "".join(g2p.word_phones(w, lang)), "score": 95.0 if i in ok else 25.0,
              "phones": [], "start": None, "end": None} for i, w in enumerate(exp)]
    score = round(sum(w["score"] for w in words) / max(1, len(words)), 1)
    dur = tr.get("duration") or 0
    return {"engine": "whisper", "score": score, "words": words, "transcript": tr["text"],
            "tips": [], "expected_ipa": g2p.ipa(text, lang),
            "fluency": {"wpm": round(len(got) / (dur / 60)) if dur else 0, "long_pauses": 0, "duration": dur},
            "phone_scores": []}


def _record_pron(lang: str, text: str, result: dict, mode: str):
    db.execute("INSERT INTO pron_attempts(lang, text, score, mode, ts) VALUES (?,?,?,?,?)",
               (lang, text, result["score"], mode, db.now_iso()))
    for ph, sc in result.get("phone_scores", []):
        row = db.one("SELECT * FROM phoneme_stats WHERE lang=? AND phoneme=?", (lang, ph))
        recent = (json.loads(row["recent"]) if row else []) + [sc]
        recent = recent[-20:]
        db.execute(
            "INSERT INTO phoneme_stats(lang, phoneme, attempts, total, recent) VALUES (?,?,1,?,?) "
            "ON CONFLICT(lang, phoneme) DO UPDATE SET attempts=attempts+1, total=total+?, recent=?",
            (lang, ph, sc, json.dumps(recent), sc, json.dumps(recent)),
        )
    # En conversación la pronunciación suma estadística de fonemas, pero no cuenta como ejercicio aparte.
    if mode != "conversation":
        db.log_activity(lang, "pronunciation", xp=max(1, round(result["score"] / 20)), minutes=0.6,
                        detail={"score": result["score"], "mode": mode})


@router.get("/practice/weak")
def practice_weak(lang: str | None = None):
    from .phoneme_tips import tip_for
    lang = L(lang)
    return [{**w, **tip_for(lang, w["phoneme"])} for w in planner.weak_phonemes(lang, 8)]


@router.get("/practice/minimal-pairs")
def minimal_pairs(lang: str | None = None):
    from .phoneme_tips import tip_for
    lang = L(lang)
    weak = {w["phoneme"] for w in planner.weak_phonemes(lang, 8)}
    out = []
    for c in content.minimal_pairs(lang):
        out.append({**c, "tip_a": tip_for(lang, c["a"]), "tip_b": tip_for(lang, c["b"]),
                    "recommended": c["a"] in weak or c["b"] in weak})
    return out


class ListenResult(BaseModel):
    lang: str = "en"
    kind: str = "listening"   # listening | dictation
    correct: int = 0
    total: int = 0
    detail: dict = {}


@router.post("/practice/listen-result")
def listen_result(r: ListenResult):
    lang = L(r.lang)
    kind = r.kind if r.kind in ("listening", "dictation") else "listening"
    db.log_activity(lang, kind, xp=max(1, r.correct), minutes=max(0.5, r.total * 0.25),
                    detail={"correct": r.correct, "total": r.total, **r.detail})
    return {"ok": True}


# =====================================================================
# Vocabulario y repaso espaciado
# =====================================================================

@router.get("/vocab")
def vocab(lang: str | None = None, level: str | None = None, category: str | None = None,
          q: str | None = None, limit: int = 200, offset: int = 0):
    lang = L(lang)
    words = content.vocab(lang)
    deck = {r["front"].lower(): r for r in db.query(
        "SELECT front, state FROM cards WHERE lang=? AND kind='word'", (lang,))}
    if level:
        words = [w for w in words if w.get("level") == level]
    if category:
        words = [w for w in words if w.get("category") == category]
    if q:
        ql = q.lower().strip()
        words = [w for w in words if ql in w["word"].lower() or ql in w.get("translation", "").lower()]
    cats = sorted({w.get("category", "otros") for w in content.vocab(lang)})
    page = words[offset: offset + limit]
    return {
        "total": len(words), "categories": cats,
        "words": [{**w, "in_deck": w["word"].lower() in deck,
                   "known": deck.get(w["word"].lower(), {}).get("state") == 2} for w in page],
    }


class CardIn(BaseModel):
    lang: str = "en"
    kind: str = "word"
    front: str
    back: str
    extra: dict = {}
    source: str = "manual"


@router.post("/cards")
def add_card(c: CardIn):
    if c.kind not in ("word", "sentence", "mistake", "phrase"):
        raise HTTPException(400, "tipo inválido")
    return {"id": srs.add_card(L(c.lang), c.kind, c.front, c.back, c.extra, c.source)}


class BulkIn(BaseModel):
    lang: str = "en"
    count: int = 20
    level: str | None = None
    category: str | None = None


@router.post("/cards/bulk")
def add_bulk(b: BulkIn):
    """Añade al mazo las siguientes N palabras más frecuentes que aún no tienes."""
    lang = L(b.lang)
    have = {r["front"].lower() for r in db.query("SELECT front FROM cards WHERE lang=? AND kind='word'", (lang,))}
    added = 0
    for w in content.vocab(lang):
        if added >= b.count:
            break
        if w["word"].lower() in have or (b.level and w.get("level") != b.level) \
                or (b.category and w.get("category") != b.category):
            continue
        srs.add_card(lang, "word", w["word"], w["translation"],
                     {"example": w.get("example"), "example_es": w.get("example_es"),
                      "pos": w.get("pos"), "level": w.get("level")}, "frequency")
        added += 1
    return {"added": added}


@router.post("/cards/{card_id}/mnemonic")
async def card_mnemonic(card_id: int):
    """Truco para recordar una palabra difícil (palabra clave en español, cognado, imagen mental)."""
    row = db.one("SELECT * FROM cards WHERE id=?", (card_id,))
    if not row:
        raise HTTPException(404, "tarjeta no encontrada")
    extra = json.loads(row["extra"] or "{}")
    if extra.get("mnemonic"):
        return {"mnemonic": extra["mnemonic"]}
    try:
        res = await llm.json_call(
            f"You help a Spanish speaker memorise {TARGET[row['lang']]} vocabulary. Create ONE short, vivid memory trick IN SPANISH: "
            "use the keyword method (a Spanish word that sounds similar + a funny mental image linking it to the meaning), "
            "or a cognate/etymology link if there is a good one. Max 2 sentences. Return ONLY JSON {\"mnemonic\": \"...\"}",
            f"Word/expression: {row['front']}\nMeaning: {row['back']}",
            model=config.LLM_FAST_MODEL, temperature=0.8, max_tokens=500,
        )
    except llm.LLMError as e:
        _llm_error(e)
    extra["mnemonic"] = res.get("mnemonic", "")
    db.execute("UPDATE cards SET extra=? WHERE id=?", (json.dumps(extra, ensure_ascii=False), card_id))
    return {"mnemonic": extra["mnemonic"]}


@router.get("/packs")
def packs_list(lang: str | None = None):
    lang = L(lang)
    have = {r["front"].lower() for r in db.query("SELECT front FROM cards WHERE lang=? AND kind='phrase'", (lang,))}
    out = []
    for p in content.packs(lang):
        n_in = sum(1 for it in p["items"] if it["t"].lower() in have)
        out.append({k: p[k] for k in ("id", "level", "title", "description")} | {"total": len(p["items"]), "in_deck": n_in})
    return out


@router.get("/packs/{pack_id}")
def pack_get(pack_id: str, lang: str | None = None):
    lang = L(lang)
    p = next((p for p in content.packs(lang) if p["id"] == pack_id), None)
    if not p:
        raise HTTPException(404, "paquete no encontrado")
    have = {r["front"].lower() for r in db.query("SELECT front FROM cards WHERE lang=? AND kind='phrase'", (lang,))}
    return {**p, "items": [{**it, "in_deck": it["t"].lower() in have} for it in p["items"]]}


class PackAdd(BaseModel):
    lang: str = "en"
    count: int = 15


@router.post("/packs/{pack_id}/add")
def pack_add(pack_id: str, a: PackAdd):
    lang = L(a.lang)
    p = next((p for p in content.packs(lang) if p["id"] == pack_id), None)
    if not p:
        raise HTTPException(404, "paquete no encontrado")
    have = {r["front"].lower() for r in db.query("SELECT front FROM cards WHERE lang=? AND kind='phrase'", (lang,))}
    added = 0
    for it in p["items"]:
        if added >= a.count:
            break
        if it["t"].lower() in have:
            continue
        srs.add_card(lang, "phrase", it["t"], it["es"],
                     {"example": it.get("example"), "example_es": it.get("example_es"), "note": it.get("note"), "pack": pack_id},
                     "pack")
        added += 1
    return {"added": added}


@router.delete("/cards/{card_id}")
def suspend_card(card_id: int):
    db.execute("UPDATE cards SET suspended=1 WHERE id=?", (card_id,))
    return {"ok": True}


@router.get("/srs/queue")
def srs_queue(lang: str | None = None, kinds: str | None = None):
    return srs.queue(L(lang), limit=100, kinds=kinds.split(",") if kinds else None)


class ReviewIn(BaseModel):
    card_id: int
    rating: str
    seconds: float = 8


@router.post("/srs/review")
def srs_review(r: ReviewIn):
    try:
        res = srs.review(r.card_id, r.rating)
    except KeyError:
        raise HTTPException(404, "tarjeta no encontrada")
    row = db.one("SELECT lang FROM cards WHERE id=?", (r.card_id,))
    db.log_activity(row["lang"], "srs", xp=1, minutes=min(r.seconds, 60) / 60)
    return res


@router.get("/srs/stats")
def srs_stats(lang: str | None = None):
    return srs.stats(L(lang))


@router.get("/mistakes")
def mistakes(lang: str | None = None, limit: int = 200):
    return db.query("SELECT * FROM mistakes WHERE lang=? ORDER BY id DESC LIMIT ?", (L(lang), limit))


# =====================================================================
# Gramática y escritura
# =====================================================================

@router.get("/grammar")
def grammar_list(lang: str | None = None):
    lang = L(lang)
    prog = {r["lesson_id"]: r for r in db.query("SELECT * FROM grammar_progress WHERE lang=?", (lang,))}
    return [{"id": l["id"], "level": l["level"], "title": l["title"], "summary": l.get("summary", ""),
             "exercises": len(l.get("exercises", [])),
             "best_score": (prog.get(l["id"]) or {}).get("best_score"),
             "completed": bool((prog.get(l["id"]) or {}).get("completed"))}
            for l in content.grammar(lang)]


@router.get("/grammar/{lesson_id}")
def grammar_lesson(lesson_id: str, lang: str | None = None):
    l = content.lesson(L(lang), lesson_id)
    if not l:
        raise HTTPException(404, "lección no encontrada")
    return l


class OpenCheck(BaseModel):
    lang: str = "en"
    type: str
    prompt: str
    answer: str
    expected: str


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").strip()
    return re.sub(r"[^\w' ]", "", re.sub(r"\s+", " ", s)).strip()


@router.post("/grammar/check-open")
async def grammar_check_open(c: OpenCheck):
    """Corrige respuestas abiertas (traducir / corregir frase). Primero comparación exacta; si no, la IA."""
    if _norm(c.answer) == _norm(c.expected):
        return {"correct": True, "feedback": "¡Perfecto!", "corrected": c.expected}
    lang = L(c.lang)
    if not llm.available():
        ratio = SequenceMatcher(a=_norm(c.answer), b=_norm(c.expected)).ratio()
        return {"correct": ratio > 0.9, "feedback": "Compara con la respuesta modelo.", "corrected": c.expected}
    try:
        res = await llm.json_call(
            f"You grade a {TARGET[lang]} exercise for a Spanish speaker. Accept any grammatically correct, natural answer "
            "that keeps the meaning (not only the model answer). Return ONLY JSON "
            "{\"correct\": bool, \"feedback\": \"1-2 sentences in Spanish explaining the error or praising\", "
            "\"corrected\": \"the learner's answer minimally corrected (or the same if correct)\"}",
            f"Exercise type: {c.type}\nPrompt: {c.prompt}\nModel answer: {c.expected}\nLearner answer: {c.answer}",
            model=config.LLM_FAST_MODEL, temperature=0.1, max_tokens=700,
        )
    except llm.LLMError as e:
        _llm_error(e)
    return res


class LessonDone(BaseModel):
    lang: str = "en"
    score: float
    mistakes: list[dict] = []


@router.post("/grammar/{lesson_id}/complete")
def grammar_complete(lesson_id: str, d: LessonDone):
    lang = L(d.lang)
    prev = db.one("SELECT * FROM grammar_progress WHERE lang=? AND lesson_id=?", (lang, lesson_id))
    best = max(d.score, prev["best_score"]) if prev else d.score
    completed = (prev and prev["completed"]) or (db.now_iso() if d.score >= 70 else None)
    db.execute(
        "INSERT INTO grammar_progress(lang, lesson_id, best_score, attempts, completed) VALUES (?,?,?,1,?) "
        "ON CONFLICT(lang, lesson_id) DO UPDATE SET best_score=?, attempts=attempts+1, completed=?",
        (lang, lesson_id, best, completed, best, completed),
    )
    for m in d.mistakes[:10]:
        db.log_mistake(lang, "grammar", m.get("original", ""), m.get("corrected", ""),
                       m.get("explanation", ""), m.get("category", "gramática"))
    db.log_activity(lang, "grammar", xp=int(5 + d.score / 10), minutes=6, detail={"lesson": lesson_id, "score": d.score})
    return {"best_score": best, "completed": bool(completed)}


@router.post("/grammar/{lesson_id}/more")
async def grammar_more(lesson_id: str, lang: str | None = None):
    lang = L(lang)
    l = content.lesson(lang, lesson_id)
    if not l:
        raise HTTPException(404, "lección no encontrada")
    past = db.query("SELECT original, corrected FROM mistakes WHERE lang=? ORDER BY id DESC LIMIT 8", (lang,))
    try:
        res = await llm.json_call(
            f"Create 8 NEW {TARGET[lang]} grammar exercises for Spanish speakers about: {l['title']} (CEFR {l['level']}). "
            "Mix types. In choice exercises exactly ONE option must be correct (never two valid spellings like traveled/travelled). "
            "Return ONLY JSON {\"exercises\": [...]} using exactly these shapes: "
            "{\"type\":\"choice\",\"prompt\":\"sentence with ___\",\"options\":[3 options],\"answer\":index,\"explanation\":\"Spanish\"} "
            "{\"type\":\"fill\",\"prompt\":\"sentence with ___\",\"answer\":\"word\",\"accept\":[],\"explanation\":\"Spanish\"} "
            "{\"type\":\"fix\",\"prompt\":\"sentence with one mistake\",\"answer\":\"corrected\",\"explanation\":\"Spanish\"} "
            "{\"type\":\"translate\",\"prompt\":\"Spanish sentence\",\"answer\":\"model translation\",\"explanation\":\"Spanish\"}",
            f"Recent mistakes of this learner (use similar traps if relevant): {past}",
            temperature=0.8, max_tokens=3500,
        )
    except llm.LLMError as e:
        _llm_error(e)
    good = [e for e in res.get("exercises", []) if e.get("type") in ("choice", "fill", "fix", "translate")
            and e.get("prompt") and "answer" in e]
    good = [e for e in good if e["type"] != "choice" or (isinstance(e.get("options"), list)
                                                         and isinstance(e["answer"], int) and 0 <= e["answer"] < len(e["options"]))]
    return {"exercises": good}


class WritingIn(BaseModel):
    lang: str = "en"
    text: str
    prompt: str | None = None


@router.post("/writing/correct")
async def writing_correct(w: WritingIn):
    lang = L(w.lang)
    level = db.get_setting(f"level_{lang}", "A1")
    try:
        res = await llm.json_call(
            f"You are a kind but precise {TARGET[lang]} teacher for a Spanish speaker (CEFR {level}). Correct their text. "
            "Return ONLY JSON {\"corrected\": \"full corrected text\", "
            "\"natural\": \"a more natural native version\", "
            "\"corrections\": [{\"original\": \"the wrong phrase with enough context (3-10 words, copied from the text)\", "
            "\"corrected\": \"the same phrase corrected\", \"explanation\": \"short Spanish\", "
            "\"category\": \"tiempo verbal|preposición|artículo|orden de palabras|vocabulario|concordancia|pronombre|ortografía|expresión natural|otro\"}], "
            "\"feedback\": \"2-3 sentences in Spanish: what is good and what to work on\", \"score\": 0-100}",
            (f"Writing prompt: {w.prompt}\n" if w.prompt else "") + f"Text: {w.text}",
            temperature=0.2, max_tokens=3000,
        )
    except llm.LLMError as e:
        _llm_error(e)
    for c in res.get("corrections", [])[:12]:
        db.log_mistake(lang, "writing", c.get("original", ""), c.get("corrected", ""),
                       c.get("explanation", ""), c.get("category", "otro"))
    db.log_activity(lang, "writing", xp=10, minutes=5, detail={"score": res.get("score")})
    return res


# =====================================================================
# Lectura (input comprensible)
# =====================================================================

class ReadingIn(BaseModel):
    lang: str = "en"
    level: str | None = None
    topic: str | None = None


@router.post("/reading/generate")
async def reading_generate(r: ReadingIn):
    lang = L(r.lang)
    level = r.level or db.get_setting(f"level_{lang}", "A1")
    known = [x["front"] for x in db.query(
        "SELECT front FROM cards WHERE lang=? AND kind='word' AND state>=1 ORDER BY RANDOM() LIMIT 60", (lang,))]
    length = {"A1": "80-120", "A2": "120-180", "B1": "180-260", "B2": "250-350", "C1": "300-420"}.get(level, "150")
    try:
        res = await llm.json_call(
            f"Write an engaging short story or article in {TARGET[lang]} for a Spanish-speaking learner at CEFR {level} "
            f"({length} words). Use mostly very common words so the learner understands ~95% (comprehensible input); "
            "naturally reuse some of the learner's known words. "
            "Return ONLY JSON {\"title\": \"...\", \"title_es\": \"...\", "
            "\"paragraphs\": [{\"t\": \"paragraph\", \"es\": \"Spanish translation\"}], "
            "\"questions\": [{\"q\": \"comprehension question in the target language\", \"options\": [3 options], \"answer\": index}] (3 questions), "
            "\"vocab\": [{\"t\": \"key word or phrase\", \"es\": \"Spanish\"}] (6 items)}",
            f"Topic: {r.topic or 'anything interesting: daily life, travel, a funny situation, a mystery, culture'}. Learner's known words: {known}",
            temperature=0.9, max_tokens=3500,
        )
    except llm.LLMError as e:
        _llm_error(e)
    rid = db.execute("INSERT INTO readings(lang, level, title, data, ts) VALUES (?,?,?,?,?)",
                     (lang, level, res.get("title", "Lectura"), json.dumps(res, ensure_ascii=False), db.now_iso()))
    return {"id": rid, "level": level, **res}


class ImportIn(BaseModel):
    lang: str = "en"
    title: str = ""
    text: str


@router.post("/reading/import")
def reading_import(i: ImportIn):
    """Importa un texto propio (artículo, noticia, capítulo) para leerlo con traducción por toque y audio."""
    lang = L(i.lang)
    text = i.text.strip()[:20000]
    if len(text) < 40:
        raise HTTPException(400, "El texto es demasiado corto")
    paras = [p.strip() for p in re.split(r"\n\s*\n|\r\n\r\n", text) if p.strip()]
    if len(paras) == 1:  # sin párrafos: lo partimos cada ~4 frases
        sents = re.split(r"(?<=[.!?])\s+", paras[0])
        paras = [" ".join(sents[k:k + 4]) for k in range(0, len(sents), 4)]
    title = i.title.strip() or (paras[0][:60] + "…")
    data = {"title": title, "title_es": "", "paragraphs": [{"t": p, "es": ""} for p in paras],
            "questions": [], "vocab": [], "imported": True}
    level = db.get_setting(f"level_{lang}", "A1")
    rid = db.execute("INSERT INTO readings(lang, level, title, data, ts) VALUES (?,?,?,?,?)",
                     (lang, level, title, json.dumps(data, ensure_ascii=False), db.now_iso()))
    return {"id": rid, "level": level, **data}


@router.get("/reading/list")
def reading_list(lang: str | None = None):
    return db.query("SELECT id, level, title, read_done, ts FROM readings WHERE lang=? ORDER BY id DESC LIMIT 50", (L(lang),))


@router.get("/reading/{rid}")
def reading_get(rid: int):
    row = db.one("SELECT * FROM readings WHERE id=?", (rid,))
    if not row:
        raise HTTPException(404, "no encontrada")
    return {"id": row["id"], "level": row["level"], **json.loads(row["data"])}


class ReadingDone(BaseModel):
    score: float = 0


@router.post("/reading/{rid}/done")
def reading_done(rid: int, d: ReadingDone):
    row = db.one("SELECT lang FROM readings WHERE id=?", (rid,))
    if not row:
        raise HTTPException(404)
    db.execute("UPDATE readings SET read_done=1 WHERE id=?", (rid,))
    db.log_activity(row["lang"], "reading", xp=int(8 + d.score / 20), minutes=5, detail={"reading": rid, "score": d.score})
    return {"ok": True}


# =====================================================================
# Evaluación de nivel (MCER) por destreza
# =====================================================================

@router.get("/assessment/summary")
def assessment_summary(lang: str | None = None):
    return assessment.summary(L(lang))


@router.get("/assessment/vocab-test")
def assessment_vocab_test(lang: str | None = None):
    t = assessment.vocab_test(L(lang))
    if not t["bands"]:
        raise HTTPException(409, "Todavía no hay vocabulario para este idioma (se está generando). Inténtalo más tarde.")
    return t


class VocabTestIn(BaseModel):
    lang: str = "en"
    shown: list[str]
    known: list[str]


@router.post("/assessment/vocab-test")
def assessment_vocab_score(v: VocabTestIn):
    return assessment.score_vocab_test(L(v.lang), v.shown, v.known)


@router.get("/assessment/prompt")
def assessment_prompt(skill: str, lang: str | None = None, level: str | None = None):
    lang = L(lang)
    lvl = level or db.get_setting(f"level_{lang}", "A1")
    p = assessment.PROMPTS.get(skill, {})
    return {"skill": skill, "level": lvl, "prompt": p.get(lvl, p.get("B1", "")), "all": p}


@router.post("/assessment/speaking")
async def assessment_speaking(audio_file: UploadFile = File(..., alias="audio"), lang: str = Form("en"), prompt: str = Form(...)):
    lang = L(lang)
    data = await audio_file.read()
    try:
        tr = await stt.transcribe(data, lang)
    except llm.LLMError as e:
        _llm_error(e)
    if len(tr["text"].split()) < 8:
        raise HTTPException(422, "La grabación es demasiado corta o no se entendió. Habla al menos 30-60 segundos.")
    words = tr["words"]
    span = (words[-1]["end"] - words[0]["start"]) if len(words) > 1 else (tr.get("duration") or 1)
    metrics = {
        "words": len(words), "seconds": round(span),
        "wpm": round(len(words) / (span / 60)) if span > 1 else 0,
        "long_pauses": sum(1 for i in range(1, len(words)) if words[i]["start"] - words[i - 1]["end"] > 1.0),
    }
    # Pronunciación medida por el motor de fonemas sobre lo transcrito (si está disponible).
    try:
        if pronunciation.load():
            x, _ = audio.wav_to_float(data)
            pr = await run_in_threadpool(pronunciation.assess, audio.trim_silence(x), tr["text"][:600], lang)
            metrics["pronunciation"] = pr["score"]
    except Exception:
        pass
    try:
        res = await assessment.evaluate_speaking(lang, prompt, tr["text"], metrics)
    except llm.LLMError as e:
        _llm_error(e)
    return {**res, "metrics": metrics, "transcript": tr["text"]}


class WritingTestIn(BaseModel):
    lang: str = "en"
    prompt: str
    text: str


@router.post("/assessment/writing")
async def assessment_writing(w: WritingTestIn):
    try:
        return await assessment.evaluate_writing(L(w.lang), w.prompt, w.text)
    except llm.LLMError as e:
        _llm_error(e)


class CompIn(BaseModel):
    lang: str = "en"
    skill: str
    level: str
    score: float


@router.post("/assessment/record")
def assessment_record(c: CompIn):
    assessment.record_comprehension(L(c.lang), c.skill, c.level, c.score)
    return {"ok": True}


# =====================================================================
# Escucha activa (diálogos, pódcasts, dictogloss, resumen)
# =====================================================================

class ListenGen(BaseModel):
    lang: str = "en"
    level: str | None = None
    kind: str = "dialogue"
    topic: str | None = None


@router.post("/listening/generate")
async def listening_generate(g: ListenGen):
    lang = L(g.lang)
    try:
        return await listening.generate(lang, g.level or db.get_setting(f"level_{lang}", "A1"), g.kind, g.topic)
    except llm.LLMError as e:
        _llm_error(e)


@router.get("/listening/list")
def listening_list(lang: str | None = None):
    return db.query("SELECT id, level, kind, title, done, ts FROM listenings WHERE lang=? ORDER BY id DESC LIMIT 50", (L(lang),))


@router.get("/listening/{lid}")
def listening_get(lid: int):
    x = listening.get(lid)
    if not x:
        raise HTTPException(404, "no encontrado")
    return x


class RetellIn(BaseModel):
    lang: str = "en"
    original: str | None = None
    text: str
    source: str = "retell"   # retell | dictogloss
    listening_id: int | None = None
    score: float | None = None  # puntaje de comprensión (preguntas), si lo hubo


@router.post("/listening/retell")
async def listening_retell(r: RetellIn):
    lang = L(r.lang)
    original = r.original
    if r.listening_id:
        x = listening.get(r.listening_id)
        if x:
            original = "\n".join(l["t"] for l in x["lines"])
            db.execute("UPDATE listenings SET done=1 WHERE id=?", (r.listening_id,))
    if not original:
        raise HTTPException(400, "falta el texto original")
    level = db.get_setting(f"level_{lang}", "A1")
    try:
        res = await listening.evaluate_retell(lang, original, r.text, level, r.source)
    except llm.LLMError as e:
        _llm_error(e)
    kind = "dictation" if r.source == "dictogloss" else "listening"
    db.log_activity(lang, kind, xp=15, minutes=6, detail={"source": r.source, "content": res.get("content_score")})
    return res


@router.post("/listening/dictogloss")
async def listening_dictogloss(g: ListenGen):
    lang = L(g.lang)
    try:
        return await listening.dictogloss_text(lang, g.level or db.get_setting(f"level_{lang}", "A1"), g.topic)
    except llm.LLMError as e:
        _llm_error(e)


# =====================================================================
# Misiones y conversación
# =====================================================================

@router.get("/missions")
def missions_list(lang: str | None = None):
    return missions.list_missions(L(lang))


@router.get("/missions/{mission_id}")
def mission_get(mission_id: str, lang: str | None = None):
    m = missions.get_mission(L(lang), mission_id)
    if not m:
        raise HTTPException(404, "misión no encontrada")
    return missions.public_mission(m)


class StartIn(BaseModel):
    lang: str = "en"
    mode: str = "entrenamiento"


@router.post("/missions/{mission_id}/start")
async def mission_start(mission_id: str, s: StartIn):
    lang = L(s.lang)
    m = missions.get_mission(lang, mission_id)
    if not m:
        raise HTTPException(404, "misión no encontrada")
    try:
        return await missions.start_run(lang, m, s.mode if s.mode in ("entrenamiento", "inmersion") else "entrenamiento")
    except llm.LLMError as e:
        _llm_error(e)


class FreeIn(BaseModel):
    lang: str = "en"
    topic: str = "anything"
    mode: str = "entrenamiento"
    kind: str = "libre"


@router.get("/conversation/modes")
def conversation_modes():
    return [{"id": k, **{x: v[x] for x in ("title", "icon", "desc")}} for k, v in missions.CONVERSATION_MODES.items()]


@router.get("/profile")
def profile_get():
    return {"facts": db.get_setting("learner_profile", [])}


class ProfileIn(BaseModel):
    facts: list[str]


@router.put("/profile")
def profile_put(p: ProfileIn):
    db.set_setting("learner_profile", [f.strip() for f in p.facts if f.strip()][:30])
    return {"facts": db.get_setting("learner_profile", [])}


@router.post("/conversation/start")
async def conversation_start(f: FreeIn):
    lang = L(f.lang)
    m = missions.free_talk_mission(lang, f.topic, db.get_setting(f"level_{lang}", "A1"), f.kind)
    try:
        return await missions.start_run(lang, m, f.mode)
    except llm.LLMError as e:
        _llm_error(e)


class GenIn(BaseModel):
    lang: str = "en"
    level: str | None = None
    theme: str | None = None


@router.post("/missions/generate")
async def mission_generate(g: GenIn):
    lang = L(g.lang)
    try:
        m = await missions.generate_mission(lang, g.level or db.get_setting(f"level_{lang}", "A1"), g.theme)
    except llm.LLMError as e:
        _llm_error(e)
    return missions.public_mission(m)


class TurnIn(BaseModel):
    text: str


@router.post("/runs/{run_id}/turn")
async def run_turn(run_id: int, t: TurnIn):
    if not t.text.strip():
        raise HTTPException(400, "mensaje vacío")
    try:
        return await missions.turn(run_id, t.text.strip()[:800])
    except KeyError:
        raise HTTPException(404, "partida no encontrada")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        _llm_error(e)


@router.post("/runs/{run_id}/hint")
async def run_hint(run_id: int):
    try:
        return await missions.hint(run_id)
    except llm.LLMError as e:
        _llm_error(e)


@router.post("/runs/{run_id}/finish")
async def run_finish(run_id: int):
    try:
        return await missions.finish(run_id)
    except KeyError:
        raise HTTPException(404, "partida no encontrada")


@router.get("/runs/{run_id}")
def run_get(run_id: int):
    row = db.one("SELECT * FROM mission_runs WHERE id=?", (run_id,))
    if not row:
        raise HTTPException(404, "partida no encontrada")
    return {"run_id": run_id, "mode": row["mode"],
            "mission": missions.public_mission(json.loads(row["mission"])),
            "transcript": json.loads(row["transcript"]), "state": json.loads(row["state"]),
            "result": json.loads(row["result"]) if row["result"] else None}


@router.get("/runs")
def runs_list(lang: str | None = None):
    rows = db.query("SELECT id, mission_id, mode, result, started, finished FROM mission_runs WHERE lang=? "
                    "AND finished IS NOT NULL ORDER BY id DESC LIMIT 30", (L(lang),))
    for r in rows:
        res = json.loads(r.pop("result") or "{}")
        r["score"] = res.get("score")
        r["success"] = res.get("success")
    return rows


# =====================================================================
# Fluidez
# =====================================================================

@router.get("/fluency/topics")
def fluency_topics():
    return content.FLUENCY_TOPICS


@router.get("/fluency/mastered")
def fluency_mastered(lang: str | None = None):
    return srs.mastered(L(lang))


@router.post("/fluency/speech")
async def fluency_speech(audio_file: UploadFile = File(..., alias="audio"), lang: str = Form("en")):
    """Transcribe un monólogo y calcula palabras, palabras por minuto y pausas."""
    data = await audio_file.read()
    try:
        tr = await stt.transcribe(data, L(lang))
    except llm.LLMError as e:
        _llm_error(e)
    words = tr["words"]
    n = len(words) or len(tr["text"].split())
    span = (words[-1]["end"] - words[0]["start"]) if len(words) > 1 else (tr.get("duration") or 0)
    pauses = sum(1 for i in range(1, len(words)) if words[i]["start"] - words[i - 1]["end"] > 1.0)
    return {"text": tr["text"], "words": n, "wpm": round(n / (span / 60)) if span > 1 else 0,
            "long_pauses": pauses, "duration": tr.get("duration")}


class FluencyIn(BaseModel):
    lang: str = "en"
    kind: str
    data: dict = {}
    minutes: float = 3


@router.post("/fluency/record")
def fluency_record(f: FluencyIn):
    lang = L(f.lang)
    db.execute("INSERT INTO fluency_sessions(lang, kind, data, ts) VALUES (?,?,?,?)",
               (lang, f.kind, json.dumps(f.data, ensure_ascii=False), db.now_iso()))
    db.log_activity(lang, "fluency", xp=12, minutes=f.minutes, detail={"kind": f.kind})
    return {"ok": True}


@router.get("/fluency/history")
def fluency_history(lang: str | None = None):
    rows = db.query("SELECT * FROM fluency_sessions WHERE lang=? ORDER BY id DESC LIMIT 50", (L(lang),))
    for r in rows:
        r["data"] = json.loads(r["data"])
    return rows
