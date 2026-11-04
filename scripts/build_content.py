"""Genera el CONTENIDO FIJO de la app con IA (se ejecuta una sola vez, no en cada uso).

  python scripts/build_content.py            # todo
  python scripts/build_content.py en vocab   # solo una parte

Es reanudable: guarda el avance en content/_build/ y si lo cortas sigue donde iba.
Usa varios modelos en paralelo porque cada uno tiene su propio límite de tokens/minuto.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app import llm  # noqa: E402
from syllabus import PACKS, SYLLABUS  # noqa: E402

CONTENT = ROOT / "content"
BUILD = CONTENT / "_build"
BUILD.mkdir(parents=True, exist_ok=True)

from app.config import TARGET_NAMES as LANG_NAMES  # noqa: E402
VOCAB_SIZE = {"en": 5000, "fr": 4000, "pt": 3000, "de": 3000}
PACK_BATCH = 25
FAST = "--fast" in sys.argv
GRAMMAR_MODEL = "openai/gpt-oss-120b"
GRAMMAR_PER_DAY = 10  # ~50.000 tokens: deja ~150.000 diarios del modelo grande para la app


def _quota_file() -> Path:
    return ROOT / "content" / "_build" / "_grammar_quota.json"


def _grammar_used_today() -> int:
    import datetime as _dt
    try:
        q = json.loads(_quota_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    return q.get("count", 0) if q.get("day") == _dt.date.today().isoformat() else 0


def _grammar_count_one():
    import datetime as _dt
    today = _dt.date.today().isoformat()
    n = _grammar_used_today() + 1
    _quota_file().parent.mkdir(parents=True, exist_ok=True)
    _quota_file().write_text(json.dumps({"day": today, "count": n}), encoding="utf-8")
VOCAB_BATCH = 40
SENT_PER_LEVEL = 80
SENT_BATCH = 20
LEVELS = ["A1", "A2", "B1", "B2", "C1"]

CATEGORIES = [
    "personas y familia", "cuerpo y salud", "comida y bebida", "casa", "ciudad y lugares",
    "viajes y transporte", "trabajo y estudios", "naturaleza y clima", "tiempo y calendario",
    "números y cantidades", "emociones y carácter", "comunicación", "compras y dinero",
    "ocio y deportes", "tecnología", "verbos comunes", "adjetivos comunes",
    "palabras funcionales", "otros",
]

LEVEL_GUIDE = {
    "A1": "very short (4-7 words), present tense, the 500 most common words, everyday survival situations",
    "A2": "short (6-10 words), simple past/future, common daily topics, 1000 most common words",
    "B1": "8-14 words, mixed tenses, opinions, plans, experiences, travel and work",
    "B2": "12-20 words, conditionals, passive, nuanced opinions, news, work, abstract topics",
    "C1": "15-25 words, idiomatic and natural, complex structures, nuance, idioms",
}

SENT_TOPICS = [
    "greetings, introductions, family, home, daily routine",
    "food, restaurants, shopping, money, clothes",
    "travel, transport, directions, hotels, airports, weather",
    "work, study, health, doctor, emergencies, feelings, hobbies, technology",
]

# Qwen no sirve para generar en lote: en el plan gratuito solo da ~1.000 tokens de salida por minuto.
WORKER_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
GRAMMAR_MODELS = {"openai/gpt-oss-120b"}


def load_part(name: str) -> dict:
    p = BUILD / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_part(name: str, data: dict):
    (BUILD / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- vocabulario

def frequency_words(lang: str) -> list[str]:
    from wordfreq import top_n_list

    pat = {
        "en": re.compile(r"[a-z]+(?:'[a-z]+)?"),
        "fr": re.compile(r"[a-zàâæçéèêëîïôœùûüÿ]+(?:-[a-zàâæçéèêëîïôœùûüÿ]+)?"),
        "pt": re.compile(r"[a-záàâãçéêíóôõúü]+(?:-[a-záàâãçéêíóôõúü]+)?"),
        "de": re.compile(r"[a-zäöüß]+"),
    }[lang]
    keep1 = {"en": {"a", "i"}, "fr": {"a", "à", "y"}, "pt": {"a", "o", "e", "é", "à"}, "de": set()}[lang]
    out, seen = [], set()
    top = top_n_list(lang, 15000)
    topset = set(top)
    for w in top:
        if not pat.fullmatch(w) or (len(w) == 1 and w not in keep1) or w in seen:
            continue
        # Alemán: descarta grafías sin diéresis ("fuer") si existe la buena ("für").
        if lang == "de" and re.search(r"ae|oe|ue", w):
            if w.replace("ae", "ä").replace("oe", "ö").replace("ue", "ü") in topset:
                continue
        seen.add(w)
        out.append(w)
        if len(out) >= VOCAB_SIZE[lang]:
            break
    return out


def vocab_prompt(lang: str, words: list[str]) -> tuple[str, str]:
    system = (
        f"You build a {LANG_NAMES[lang]} vocabulary course for Spanish speakers. "
        "Return ONLY JSON: {\"items\": [[word, spanish_translation, pos, category, example, example_es], ...]} "
        "with exactly one item per input word, same order. "
        "spanish_translation: the 1-3 most common meanings, comma separated, short. "
        "pos: noun|verb|adj|adv|pron|prep|conj|det|num|interj|other. "
        f"category: one of {CATEGORIES}. "
        f"example: a natural, simple {LANG_NAMES[lang]} sentence (max 10 words) using the word in its most common meaning. "
        "example_es: its Spanish translation."
        + (" For German NOUNS write the word capitalised WITH its article (e.g. 'das Haus', 'die Zeit'); "
           "for verbs the infinitive." if lang == "de" else "")
    )
    return system, json.dumps(words, ensure_ascii=False)


def validate_vocab(res: dict, words: list[str]) -> list[dict]:
    items = res.get("items") or []
    out = []
    for it in items:
        if isinstance(it, list) and len(it) >= 6 and isinstance(it[0], str):
            cat = it[3] if it[3] in CATEGORIES else "otros"
            out.append({"word": it[0].strip(), "translation": str(it[1]).strip(), "pos": str(it[2]),
                        "category": cat, "example": str(it[4]).strip(), "example_es": str(it[5]).strip()})
    if len(out) < len(words) * 0.8:
        raise ValueError(f"vocab incompleto {len(out)}/{len(words)}")
    return out


# ---------------------------------------------------------------- frases

def sentence_prompt(lang: str, level: str, topic: str, n: int) -> tuple[str, str]:
    system = (
        f"You write {LANG_NAMES[lang]} practice sentences for Spanish-speaking learners at CEFR {level}. "
        f"Level guide: {LEVEL_GUIDE[level]}. Sentences must be natural things real people say, "
        "useful, varied (statements, questions, requests), and good for pronunciation practice. "
        "Return ONLY JSON: {\"items\": [[sentence, spanish_translation], ...]}."
    )
    return system, f"Write {n} different sentences about: {topic}."


def validate_sentences(res: dict, n: int) -> list[list[str]]:
    items = [it for it in (res.get("items") or []) if isinstance(it, list) and len(it) >= 2]
    if len(items) < n * 0.7:
        raise ValueError("pocas frases")
    return [[str(a).strip(), str(b).strip()] for a, b, *_ in items]


# ---------------------------------------------------------------- paquetes

def pack_prompt(lang: str, item_desc: str, subtheme: str, title: str) -> tuple[str, str]:
    system = (
        f"You build advanced {LANG_NAMES[lang]} vocabulary packs for Spanish speakers aiming at C1. "
        "Return ONLY JSON: {\"items\": [[expression, spanish_meaning, example, example_es, note], ...]}. "
        "expression: the item in its base/dictionary form. spanish_meaning: short natural Spanish equivalent. "
        f"example: a natural, modern {LANG_NAMES[lang]} sentence (max 16 words) as a native would say it. "
        "example_es: its Spanish translation. note: very short usage note in Spanish (register, grammar, typical mistake) or empty string. "
        "Only include items that real native speakers actually use today. No duplicates."
    )
    return system, f"Pack: {title}. Give {PACK_BATCH} items, each being {item_desc}. Subgroup: {subtheme}."


def validate_pack(res: dict) -> list[dict]:
    out = []
    for it in res.get("items") or []:
        if isinstance(it, list) and len(it) >= 4 and isinstance(it[0], str) and it[0].strip():
            out.append({"t": it[0].strip(), "es": str(it[1]).strip(), "example": str(it[2]).strip(),
                        "example_es": str(it[3]).strip(), "note": str(it[4]).strip() if len(it) > 4 else ""})
    if len(out) < PACK_BATCH * 0.6:
        raise ValueError("paquete incompleto")
    return out


# ---------------------------------------------------------------- gramática

GRAMMAR_SYSTEM = """You are an expert {lang} teacher for Spanish speakers. Write one grammar lesson.
Return ONLY JSON with this exact shape:
{{
 "summary": "one sentence in Spanish: what you will learn",
 "explanation": "clear explanation IN SPANISH using Markdown (short paragraphs, bullet lists, and a small table if useful). 150-300 words. Compare with Spanish when it helps.",
 "examples": [{{"t": "{lang} sentence", "es": "Spanish translation"}}],   (5 examples)
 "common_mistakes": [{{"wrong": "...", "right": "...", "why": "short reason in Spanish"}}],   (3 items, typical of Spanish speakers)
 "exercises": [   (exactly 10, in this order: 3 choice, 3 fill, 2 order, 1 fix, 1 translate)
   {{"type": "choice", "prompt": "{lang} sentence with ___", "options": ["a","b","c"], "answer": 0, "explanation": "Spanish"}},
   {{"type": "fill", "prompt": "{lang} sentence with ___ (base word in parentheses if needed)", "answer": "correct word(s)", "accept": ["other valid answers"], "explanation": "Spanish"}},
   {{"type": "order", "words": ["words","in","correct","order"], "answer": "full correct sentence", "explanation": "Spanish"}},
   {{"type": "fix", "prompt": "{lang} sentence with ONE mistake", "answer": "corrected sentence", "explanation": "Spanish"}},
   {{"type": "translate", "prompt": "Spanish sentence to translate", "answer": "model {lang} translation", "explanation": "Spanish"}}
 ]
}}
"answer" in choice is the index of the correct option. Keep exercises at the lesson's CEFR level."""


def validate_grammar(res: dict) -> dict:
    ex = res.get("exercises") or []
    good = []
    for e in ex:
        t = e.get("type")
        if t == "choice" and isinstance(e.get("options"), list) and isinstance(e.get("answer"), int) \
                and 0 <= e["answer"] < len(e["options"]):
            good.append(e)
        elif t in ("fill", "fix", "translate") and e.get("prompt") and e.get("answer"):
            good.append(e)
        elif t == "order" and e.get("answer"):
            e["words"] = e["answer"].replace(",", " ,").replace("?", " ?").replace(".", " .").replace("!", " !").split()
            good.append(e)
    # Sin ejercicios repetidos (mismo enunciado).
    seen, uniq = set(), []
    for e in good:
        k = (e.get("type"), (e.get("prompt") or e.get("answer") or "").strip().lower())
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    good = uniq
    if len(good) < 7 or not res.get("explanation"):
        raise ValueError("lección incompleta")
    # Algunos modelos devuelven los saltos de línea escapados ("\\n" literal).
    res["explanation"] = res["explanation"].replace("\\n", "\n")
    res["exercises"] = good
    return res


# ---------------------------------------------------------------- motor

async def call(model: str, system: str, user: str, max_tokens: int) -> dict:
    for attempt in range(8):
        try:
            return await llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                json_mode=True, model=model, fallbacks=False, temperature=0.5, max_tokens=max_tokens,
            )
        except llm.LLMError as e:
            msg = str(e)
            if "401" in msg or "DIARIO" in msg:
                raise
            wait = 20 if "límite" in msg else 5
            print(f"   [{model}] reintento {attempt + 1}: {msg[:120]} (espera {wait}s)", flush=True)
            await asyncio.sleep(wait)
    raise llm.LLMError("demasiados reintentos")


async def run(langs: list[str], parts: list[str], wait_daily: bool = True):
    """Genera todo lo pendiente. Las tareas se hacen por PRIORIDAD (lo esencial primero) y,
    si se agota el límite diario de Groq, espera y sigue sola (wait_daily)."""
    tasks: list[tuple] = []   # (prioridad, orden_idioma, tarea)
    gtasks: list[tuple] = []
    stores: dict[str, dict] = {}
    for li, lang in enumerate(langs):
        if "sentences" in parts:
            name = f"{lang}_sentences"
            stores[name] = load_part(name)
            for level in LEVELS:
                for b in range(SENT_PER_LEVEL // SENT_BATCH):
                    key = f"{level}-{b}"
                    if key not in stores[name]:
                        tasks.append((1, li, ("sent", lang, name, key, (level, SENT_TOPICS[b % len(SENT_TOPICS)]))))
        if "vocab" in parts:
            name = f"{lang}_vocab"
            stores[name] = load_part(name)
            words = frequency_words(lang)
            for i in range(0, len(words), VOCAB_BATCH):
                key = str(i)
                if key not in stores[name]:
                    # Las 2.000 palabras más frecuentes son lo más rentable: van antes.
                    tasks.append((2 if i < 2000 else 4, li, ("vocab", lang, name, key, words[i: i + VOCAB_BATCH])))
        if "packs" in parts:
            name = f"{lang}_packs"
            stores[name] = load_part(name)
            for pid, level, title, desc, item_desc, subs in PACKS.get(lang, []):
                for k, sub in enumerate(subs):
                    key = f"{pid}#{k}"
                    if key not in stores[name]:
                        tasks.append((3, li, ("pack", lang, name, key, (item_desc, sub, title))))
        if "grammar" in parts:
            name = f"{lang}_grammar"
            stores[name] = load_part(name)
            for lid, level, title, points in SYLLABUS.get(lang, []):
                if lid not in stores[name]:
                    gtasks.append((0, li, ("grammar", lang, name, lid, (level, title, points))))
    tasks.sort(key=lambda t: (t[0], t[1]))
    general = [t[2] for t in tasks]
    grammar = [t[2] for t in gtasks]

    total = len(general) + len(grammar)
    print(f"Tareas pendientes: {total} (gramática: {len(grammar)})", flush=True)
    done = 0
    failures: dict = {}
    since_assemble = 0

    async def worker(model: str, kinds: set[str]):
        nonlocal done, since_assemble
        while True:
            grammar_ok = FAST or _grammar_used_today() < GRAMMAR_PER_DAY
            if "grammar" in kinds and grammar and grammar_ok:
                queue = grammar
            elif "general" in kinds and general:
                queue = general
            elif "grammar" in kinds and grammar:
                # Tope diario alcanzado: el resto del modelo grande queda para tus conversaciones.
                print(f"   ⏸️  Hoy ya se redactaron {GRAMMAR_PER_DAY} lecciones; sigo mañana.", flush=True)
                if not wait_daily:
                    return
                await asyncio.sleep(1800)
                continue
            else:
                return
            task = queue.pop(0)
            kind, lang, name, key, payload = task
            try:
                if kind == "vocab":
                    s, u = vocab_prompt(lang, payload)
                    res = validate_vocab(await call(model, s, u, 4000), payload)
                elif kind == "pack":
                    item_desc, sub, title = payload
                    s, u = pack_prompt(lang, item_desc, sub, title)
                    res = validate_pack(await call(model, s, u, 3500))
                elif kind == "sent":
                    level, topic = payload
                    s, u = sentence_prompt(lang, level, topic, SENT_BATCH)
                    res = [[a, b, level] for a, b in validate_sentences(await call(model, s, u, 3000), SENT_BATCH)]
                else:
                    level, title, points = payload
                    s = GRAMMAR_SYSTEM.format(lang=LANG_NAMES[lang])
                    u = f"Lesson: {title} (CEFR {level}). Key points: {points}."
                    res = validate_grammar(await call(model, s, u, 7000))
                    res.update({"id": key, "level": level, "title": title, "model": model})
                    _grammar_count_one()
                stores[name][key] = res
                save_part(name, stores[name])
                done += 1
                since_assemble += 1
                print(f"[{done}/{total}] {name} {key} ✓ ({model})", flush=True)
                if since_assemble >= 15:  # la app ve el contenido nuevo sin esperar al final
                    since_assemble = 0
                    assemble(langs, quiet=True)
            except Exception as e:
                msg = str(e)
                if "DIARIO" in msg:
                    queue.insert(0, task)
                    assemble(langs, quiet=True)
                    if not wait_daily:
                        print(f"   ⏸️  {model}: límite diario agotado. Vuelve a ejecutar el script más tarde.", flush=True)
                        return
                    print(f"   ⏸️  {model}: límite diario de Groq agotado; espero 15 min y sigo "
                          "(puedes cerrar la ventana cuando quieras: sigue donde se quedó).", flush=True)
                    await asyncio.sleep(900)
                    continue
                print(f"   ✗ {name} {key}: {msg[:150]}", flush=True)
                if "401" in msg:
                    raise SystemExit("Clave de API inválida: revisa GROQ_API_KEY en .env")
                failures[(name, key)] = failures.get((name, key), 0) + 1
                if failures[(name, key)] < 3:
                    queue.append(task)
                await asyncio.sleep(3)

    # Vocabulario, frases y paquetes: modelo pequeño (lo hace bien).
    # Gramática: SOLO el modelo grande (el pequeño comete errores en explicaciones y tablas),
    # con un tope diario para no dejar a la app sin él. Con "--fast" no hay tope.
    workers = [worker("openai/gpt-oss-20b", {"general"}),
               worker(GRAMMAR_MODEL, {"grammar", "general"} if FAST else {"grammar"})]
    await asyncio.gather(*workers)
    assemble(langs)


# Fragmentos de contracciones y nombres de persona que aparecen en las listas de frecuencia
# pero no son vocabulario útil para estudiar.
DROP_WORDS = {
    "don", "didn", "doesn", "isn", "wasn", "couldn", "wouldn", "shouldn", "aren", "haven", "hasn",
    "weren", "ll", "ve", "re", "ain", "im", "ive", "dont", "cant", "qu", "aujourd", "ii", "iii", "st",
    "john", "jesus", "philippe", "charles", "nicolas", "louis", "jacques", "michel", "paul", "william",
    "smith", "obama", "macron", "trump", "biden", "facebook", "twitter", "google", "youtube", "etats",
}
KEEP_PROPER = {"internet", "i"}


def _is_noise(w: dict) -> bool:
    word, tr = w["word"].lower(), w.get("translation", "")
    if word in DROP_WORDS:
        return True
    if any(k in tr.lower() for k in ("nombre propio", "apellido")):
        return True
    # Nombre de persona o marca: la "traducción" es la misma palabra con mayúscula (David, Tom, Johnson).
    if word not in KEEP_PROPER and tr.split(",")[0].strip() == word.capitalize():
        return True
    return False


def assemble(langs: list[str], quiet: bool = False):
    """Une las partes en los archivos finales content/<lang>/*.json."""
    from wordfreq import zipf_frequency

    for lang in langs:
        d = CONTENT / lang
        d.mkdir(parents=True, exist_ok=True)
        v = load_part(f"{lang}_vocab")
        if v:
            words, seen = [], set()
            for key in sorted(v, key=int):
                for it in v[key]:
                    w = it["word"].lower()
                    if w in seen or _is_noise(it):
                        continue
                    seen.add(w)
                    rank = len(words) + 1
                    it["rank"] = rank
                    it["level"] = ("A1" if rank <= 500 else "A2" if rank <= 1200 else "B1" if rank <= 2000
                                   else "B2" if rank <= 3200 else "C1")
                    it["zipf"] = round(zipf_frequency(w, lang), 2)
                    words.append(it)
            (d / "vocab.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
            quiet or print(f"{lang}: vocab {len(words)}")
        s = load_part(f"{lang}_sentences")
        if s:
            sents, seen = [], set()
            for key in sorted(s):
                for text, es, level in s[key]:
                    if text.lower() in seen:
                        continue
                    seen.add(text.lower())
                    sents.append({"text": text, "translation": es, "level": level})
            (d / "sentences.json").write_text(json.dumps(sents, ensure_ascii=False, indent=1), encoding="utf-8")
            quiet or print(f"{lang}: frases {len(sents)}")
        pk = load_part(f"{lang}_packs")
        if pk:
            packs = []
            for pid, level, title, desc, _item, subs in PACKS.get(lang, []):
                items, seen = [], set()
                for k in range(len(subs)):
                    for it in pk.get(f"{pid}#{k}", []):
                        if it["t"].lower() not in seen:
                            seen.add(it["t"].lower())
                            items.append(it)
                if items:
                    packs.append({"id": pid, "level": level, "title": title, "description": desc, "items": items})
            (d / "packs.json").write_text(json.dumps(packs, ensure_ascii=False, indent=1), encoding="utf-8")
            quiet or print(f"{lang}: paquetes {len(packs)} ({sum(len(p['items']) for p in packs)} expresiones)")
        g = load_part(f"{lang}_grammar")
        if g:
            order = [lid for lid, *_ in SYLLABUS.get(lang, [])]
            lessons = [g[i] for i in order if i in g]
            (d / "grammar.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=1), encoding="utf-8")
            quiet or print(f"{lang}: lecciones {len(lessons)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    ALL = ["en", "fr", "pt", "de"]
    langs = [a for a in args if a in ALL] or ALL
    parts = [a for a in args if a in ("vocab", "sentences", "grammar", "packs")] or ["vocab", "sentences", "grammar", "packs"]
    if "assemble" in args:
        assemble(langs)
    else:
        asyncio.run(run(langs, parts, wait_daily="--no-wait" not in args))
