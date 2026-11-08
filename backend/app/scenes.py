"""Escenas pregeneradas + enrutador local: misiones que casi no gastan cuota de Groq.

Idea (basada en el informe de investigación): en vez de llamar a la IA en CADA turno,
una vez por misión se genera un "paquete de escena" con las intenciones que se esperan
del alumno (con varias formas de decirlas) y la respuesta del personaje a cada una.

En cada turno:
  1. Tu frase (de Whisper o escrita) se compara LOCALMENTE con las intenciones esperadas
     usando un modelo pequeño de similitud de frases (multilingüe, en CPU).
  2. Si encaja → el personaje responde con la línea preparada (0 tokens).
  3. Si no encaja → (si hay cuota) un turno de IA compacto; si no, el personaje te reconduce
     hacia el objetivo pendiente con una línea preparada.
Las correcciones se dan al final, en el informe (la corrección turno a turno no mostró
ventaja clara en el metaanálisis de sistemas de diálogo).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

import numpy as np

from . import config, content, db, llm
from .config import TARGET_NAMES

log = logging.getLogger("scenes")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
THRESHOLD = 0.62      # similitud mínima para aceptar una intención
MARGIN = 0.03         # ventaja mínima sobre la segunda mejor (si son de distinto objetivo)

_tok = None
_model = None
_lock = threading.Lock()
_status = {"state": "not_loaded"}
_emb_cache: dict[str, np.ndarray] = {}


# ----------------------------------------------------------------- embeddings

def load() -> bool:
    global _tok, _model
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            _status["state"] = "loading"
            from huggingface_hub import snapshot_download
            from transformers import AutoModel, AutoTokenizer
            path = snapshot_download(EMBED_MODEL, allow_patterns=[
                "*.json", "*.txt", "model.safetensors", "sentencepiece.bpe.model", "tokenizer*", "unigram.json"])
            _tok = AutoTokenizer.from_pretrained(path)
            m = AutoModel.from_pretrained(path)
            m.eval()
            _model = m
            _status["state"] = "ready"
            return True
        except Exception as e:
            _status.update(state="unavailable", error=str(e))
            log.warning("Modelo de similitud no disponible: %s", e)
            return False


def preload_async():
    threading.Thread(target=load, daemon=True).start()


def status() -> dict:
    return dict(_status)


def embed(texts: list[str]) -> np.ndarray:
    import torch
    if not load():
        raise RuntimeError("modelo de similitud no disponible")
    missing = [t for t in texts if t not in _emb_cache]
    if missing:
        with torch.inference_mode():
            enc = _tok(missing, padding=True, truncation=True, max_length=64, return_tensors="pt")
            out = _model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            vec = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            vec = torch.nn.functional.normalize(vec, dim=1).numpy()
        for t, v in zip(missing, vec):
            _emb_cache[t] = v
    return np.stack([_emb_cache[t] for t in texts])


# ----------------------------------------------------------------- paquetes de escena

def _scene_file(lang: str) -> Path:
    return config.CONTENT_DIR / lang / "scenes.json"


def get_scene(lang: str, mission: dict) -> dict | None:
    if mission.get("scene"):
        return mission["scene"]
    f = _scene_file(lang)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8")).get(mission["id"])
        except json.JSONDecodeError:
            return None
    return None


def save_scene(lang: str, mission_id: str, scene: dict):
    f = _scene_file(lang)
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    data[mission_id] = scene
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


SCENE_PROMPT = """You prepare a role-play scene for a {target} learning game (Spanish-speaking learner, CEFR {level}).
The learner plays themselves; the character is {name}, {role} ({personality}) at {location}.
Character's secret facts / behaviour: {secret}
Complication: {complication}
Learner objectives: {objectives}
Opening line already said by the character: "{opening}"

Create the moves the learner is likely to make and the character's in-character reply to each.
Return ONLY JSON:
{{"moves": [{{"id": "m1", "objective": "o1 or null", "requires": ["ONLY if this info truly can't be given before another objective move (e.g. after a complication is solved); usually []"],
   "examples": ["6 DIFFERENT natural ways a {level} learner could say this in {target}, short, including simple/imperfect ones"],
   "reply": "character's reply in {target} (1-2 sentences, reveal facts only when asked, move the scene forward)"}}],
 "nudges": {{"o1": "character line in {target} that naturally invites the learner to work on objective o1 without giving the answer"}},
 "fallback": ["2 short in-character lines in {target} for when the character didn't understand"],
 "closing": "character's final line in {target} when all objectives are done"}}
Include 12-16 moves. EVERY objective must have at least one move (an objective like "solve the problem" needs a move where
the learner does what solves it, e.g. spelling their name), and there must be a move for EACH piece of information
the learner may ask for (each fact in the secret), plus: greeting, thanks/goodbye, asking to repeat or speak slowly,
reacting to the complication, and one small-talk move.
RULES: (1) Each secret fact appears in exactly ONE move, tagged with its objective, and that reply GIVES the info directly
(assume any earlier complication is solved; use "requires" to point to the move that solves it).
(2) Moves without objective (greetings, thanks, repeat, small talk) must NOT reveal any mission fact.
(3) Replies must NOT repeat details the learner could choose differently (sizes, quantities, names, dates);
answer generically ("Sure, coming right up") or with the character's own facts (prices, times, passwords).
Use {level}-appropriate language."""


async def generate_scene(lang: str, mission: dict) -> dict:
    target = TARGET_NAMES[lang]
    objs = "; ".join(f'{o["id"]}: {o["text"]}' for o in mission["objectives"])
    ch = mission["character"]
    res = await llm.json_call(
        SCENE_PROMPT.format(target=target, level=mission.get("level", "A2"), name=ch["name"], role=ch["role"],
                            personality=ch.get("personality", ""), location=mission.get("location", ""),
                            secret=mission.get("secret", ""), complication=mission.get("complication", ""),
                            objectives=objs, opening=mission.get("opening", "")),
        "Generate the scene JSON now.", temperature=0.6, max_tokens=5000,
        # Se genera UNA vez por misión: vale la pena usar el modelo grande (mejor cobertura).
        models=["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
    )
    return validate_scene(res, mission)


def validate_scene(res: dict, mission: dict) -> dict:
    valid_obj = {o["id"] for o in mission["objectives"]}
    moves = []
    for i, mv in enumerate(res.get("moves") or []):
        ex = [str(e).strip() for e in (mv.get("examples") or []) if str(e).strip()]
        if len(ex) < 2 or not mv.get("reply"):
            continue
        obj = mv.get("objective")
        moves.append({"id": str(mv.get("id") or f"m{i + 1}"), "objective": obj if obj in valid_obj else None,
                      "requires": [str(r) for r in (mv.get("requires") or [])], "examples": ex[:8],
                      "reply": str(mv["reply"]).strip()})
    # Solo se admiten dependencias hacia jugadas CON objetivo (p. ej. "encontrar la reserva" antes del wifi);
    # nunca hacia saludos o cortesías, que el alumno puede saltarse.
    obj_moves = {m["id"] for m in moves if m["objective"]}
    for m in moves:
        m["requires"] = [r for r in m["requires"] if r in obj_moves and r != m["id"]]
    covered = {m["objective"] for m in moves if m["objective"]}
    # Si falta como mucho UN objetivo (suele ser el del imprevisto), lo resolverá la IA en su turno.
    if len(moves) < 8 or len(covered) < max(1, len(valid_obj) - 1):
        raise ValueError(f"escena incompleta ({len(moves)} jugadas, objetivos cubiertos {sorted(covered)})")
    nudges = {k: str(v) for k, v in (res.get("nudges") or {}).items() if k in valid_obj}
    return {"moves": moves, "nudges": nudges,
            "fallback": [str(f) for f in (res.get("fallback") or [])][:3] or ["Sorry, could you say that again?"],
            "closing": str(res.get("closing") or "")}


# ----------------------------------------------------------------- enrutador

def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w' ]", " ", t.lower())).strip()


def route(scene: dict, state: dict, text: str) -> tuple[dict | None, float]:
    """Encuentra la intención esperada que mejor encaja con lo que dijo el alumno."""
    done_moves = set(state.get("moves_done", []))
    obj_of = {m["id"]: m["objective"] for m in scene["moves"] if m["objective"]}
    done_objs = set(state.get("done", []))

    def req_ok(r: str) -> bool:
        # Cumplida si hiciste esa jugada o ya lograste su objetivo por otro camino.
        return r not in obj_of or r in done_moves or obj_of[r] in done_objs
    # Las jugadas que ya cumplieron un objetivo no se repiten (salvo las de cortesía, sin objetivo).
    avail = [m for m in scene["moves"] if not (m["objective"] and m["id"] in done_moves)]
    if not avail or not text.strip():
        return None, 0.0
    examples, owners = [], []
    for m in avail:
        for e in m["examples"]:
            examples.append(e)
            owners.append(m)
    try:
        sims = embed(examples) @ embed([text])[0]
    except RuntimeError:
        # Sin modelo de similitud: coincidencia aproximada de palabras.
        from difflib import SequenceMatcher
        sims = np.array([SequenceMatcher(None, _norm(e), _norm(text)).ratio() for e in examples])
    best_per_move: dict[str, tuple[float, dict]] = {}
    for s, m in zip(sims, owners):
        # Dependencia sin cumplir (p. ej. pedir el wifi antes de encontrar la reserva): que decida la IA
        # o que el personaje reconduzca; nunca se marca el objetivo como cumplido.
        # (solo cuentan dependencias hacia jugadas con objetivo; las de saludo/cortesía se ignoran)
        if not all(req_ok(r) for r in m["requires"]):
            continue
        if s > best_per_move.get(m["id"], (-1, None))[0]:
            best_per_move[m["id"]] = (float(s), m)
    ranked = sorted(best_per_move.values(), key=lambda x: -x[0])
    best_s, best_m = ranked[0]
    if best_s < THRESHOLD:
        return None, best_s
    if len(ranked) > 1 and best_m["objective"]:
        s2, m2 = ranked[1]
        # Ambiguo solo si compiten dos jugadas de OBJETIVOS distintos: que decida la IA.
        if m2["objective"] and m2["objective"] != best_m["objective"] and best_s - s2 < MARGIN:
            return None, best_s
    return best_m, best_s


def nudge_line(scene: dict, mission: dict, state: dict) -> str:
    """Línea preparada que reconduce al alumno hacia un objetivo pendiente (sin IA)."""
    pending = [o["id"] for o in mission["objectives"] if o["id"] not in state.get("done", [])]
    misses = int(state.get("scene_misses", 0))
    if pending and scene["nudges"].get(pending[0]) and misses % 2 == 1:
        return scene["nudges"][pending[0]]
    fb = scene["fallback"]
    return fb[misses % len(fb)]
