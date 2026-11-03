"""Evaluación de pronunciación por FONEMA.

Cómo funciona:
1. espeak convierte la frase esperada en fonemas IPA (lo que DEBERÍAS decir).
2. Un modelo wav2vec2 entrenado para reconocer fonemas escucha tu audio y da, para
   cada 20 ms, la probabilidad de cada fonema.
3. Alineación forzada (Viterbi CTC): ubicamos en el tiempo cada fonema esperado.
4. Para cada fonema medimos cuánta probabilidad le dio el modelo frente a los demás
   (estilo "Goodness of Pronunciation"). Si otro fonema ganó, te decimos cuál oyó.

A diferencia de un reconocedor de palabras (Vosk/Whisper), esto NO "corrige" hacia la
palabra probable: si dices "sink" en vez de "think", el modelo oye /s/ y no /θ/.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import numpy as np

from . import config, g2p
from .phoneme_tips import tip_for

log = logging.getLogger("pronunciation")

_model = None
_fe = None
_vocab: dict[str, int] = {}
_inv: dict[int, str] = {}
_load_lock = threading.Lock()
_status = {"state": "not_loaded", "error": None}
BLANK = 0
FRAME_SEC = 0.02  # wav2vec2: un frame cada 20 ms


def status() -> dict:
    return dict(_status)


def load() -> bool:
    """Carga el modelo (una sola vez). Devuelve False si no está disponible."""
    global _model, _fe, _vocab, _inv
    if _model is not None:
        return True
    if config.PHONEME_ENGINE == "off":
        _status.update(state="disabled")
        return False
    with _load_lock:
        if _model is not None:
            return True
        try:
            _status.update(state="loading")
            import torch
            from huggingface_hub import snapshot_download
            from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

            torch.set_num_threads(max(1, (__import__("os").cpu_count() or 2)))
            path = Path(snapshot_download(
                config.PHONEME_MODEL,
                allow_patterns=["*.json", "*.txt", "pytorch_model.bin", "*.safetensors"],
            ))
            _vocab = json.loads((path / "vocab.json").read_text(encoding="utf-8"))
            _inv = {v: k for k, v in _vocab.items()}
            _fe = Wav2Vec2FeatureExtractor.from_pretrained(path)
            model = Wav2Vec2ForCTC.from_pretrained(path)
            model.eval()
            _model = model
            _status.update(state="ready", error=None)
            log.info("Modelo de fonemas listo")
            return True
        except Exception as e:  # sin torch o sin modelo → modo respaldo con Whisper
            _status.update(state="unavailable", error=str(e))
            log.warning("Motor de fonemas no disponible: %s", e)
            return False


def preload_async():
    threading.Thread(target=load, daemon=True).start()


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def _tokenize_phone(p: str) -> list[int]:
    """Fonema IPA → ids del vocabulario (si no existe entero, se divide)."""
    if p in _vocab:
        return [_vocab[p]]
    out, i = [], 0
    while i < len(p):
        for j in range(len(p), i, -1):
            if p[i:j] in _vocab:
                out.append(_vocab[p[i:j]])
                i = j
                break
        else:
            i += 1  # símbolo desconocido (p. ej. marca diacrítica suelta): se ignora
    return out


def _log_softmax(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def _ctc_force_align(logp: np.ndarray, targets: list[int]) -> list[tuple[int, int]]:
    """Viterbi CTC: para cada token objetivo devuelve (frame_inicio, frame_fin) inclusive."""
    T = logp.shape[0]
    L = len(targets)
    S = 2 * L + 1
    ext = [BLANK] * S
    for i, t in enumerate(targets):
        ext[2 * i + 1] = t
    NEG = -1e30
    dp = np.full((T, S), NEG, dtype=np.float64)
    bp = np.zeros((T, S), dtype=np.int32)
    dp[0, 0] = logp[0, BLANK]
    if S > 1:
        dp[0, 1] = logp[0, ext[1]]
    ext_arr = np.array(ext)
    # permite saltar el blank entre dos tokens distintos
    skip_ok = np.zeros(S, dtype=bool)
    for s in range(2, S):
        skip_ok[s] = ext[s] != BLANK and ext[s] != ext[s - 2]
    for t in range(1, T):
        prev = dp[t - 1]
        stay = prev
        step = np.concatenate(([NEG], prev[:-1]))
        skip = np.concatenate(([NEG, NEG], prev[:-2]))
        skip = np.where(skip_ok, skip, NEG)
        stacked = np.stack([stay, step, skip])
        best = stacked.argmax(axis=0)
        dp[t] = stacked.max(axis=0) + logp[t, ext_arr]
        bp[t] = best
    # termina en el último token o en el blank final
    s = S - 1 if S == 1 or dp[T - 1, S - 1] >= dp[T - 1, S - 2] else S - 2
    path = np.zeros(T, dtype=np.int32)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= bp[t, s]
    spans: list[list[int]] = [[-1, -1] for _ in range(L)]
    for t, s in enumerate(path):
        if s % 2 == 1:
            k = s // 2
            if spans[k][0] < 0:
                spans[k][0] = t
            spans[k][1] = t
    # tokens sin frame propio (no debería pasar): se les asigna el frame vecino
    last = 0
    for k in range(L):
        if spans[k][0] < 0:
            spans[k] = [last, last]
        last = spans[k][1]
    return [tuple(x) for x in spans]


def _greedy_decode(logp: np.ndarray) -> list[str]:
    ids = logp.argmax(axis=-1)
    out, prev = [], -1
    for i in ids:
        if i != prev and i != BLANK and i > 3:
            out.append(_inv.get(int(i), "?"))
        prev = i
    return out


# Variantes aceptables: pronunciaciones nativas válidas que espeak escribe distinto.
# No se castiga decir una variante (p. ej. "really" con /iː/ o el francés "un" como /ɛ̃/).
ALTERNATES: dict[str, dict[str, set[str]]] = {
    "en": {
        "iə": {"iː", "ɪ", "i", "ɪɹ"}, "ᵻ": {"ɪ", "ə", "i"}, "ə": {"ɪ", "ʌ", "ɐ", "ᵻ", "ɛ"},
        "ɐ": {"ə", "ʌ", "æ"}, "ɚ": {"ə", "ɜː", "ɹ"}, "i": {"iː", "ɪ"}, "ɾ": {"t", "d"},
        "ɑː": {"ɑ", "ɔ", "ɔː"}, "ɔ": {"ɑː", "ɔː", "ɑ"}, "ɔː": {"ɔ", "ɑː"}, "oʊ": {"əʊ", "o"},
        "əl": {"l", "ə"}, "ɔːɹ": {"oːɹ", "ɔː", "ɹ", "ɔ", "oʊ"}, "ɑːɹ": {"ɑː", "ɹ", "ɑ"}, "ʌ": {"ə", "ɐ"},
        "ɪ": {"ᵻ", "i"}, "ʊ": {"u"}, "t": {"ɾ", "ʔ"}, "d": {"ɾ"}, "n": {"n̩"},
        # Vocales con R: el modelo a veces las emite como vocal + ɹ por separado.
        "ɛɹ": {"ɛ", "eə", "eɪ", "ɹ", "ɚ"}, "ɪɹ": {"iə", "ɪ", "iː", "ɹ", "ɚ"},
        "ʊɹ": {"ɔːɹ", "ʊ", "uː", "ɔː", "ɹ", "ɚ"}, "aɪɚ": {"aɪə", "aɪ", "ɚ", "ɹ"},
        "oːɹ": {"ɔːɹ", "ɔː", "oʊ", "ɹ"},
    },
    "fr": {
        "œ̃": {"ɛ̃"}, "ə": {"ø", "œ"}, "ɑ": {"a"}, "a": {"ɑ"}, "e": {"ɛ"}, "ɛ": {"e"},
        "o": {"ɔ"}, "ɔ": {"o"}, "ø": {"œ", "ə"}, "œ": {"ø", "ə"},
    },
}


def _calibrate(p: float) -> float:
    """Probabilidad bruta (0-1) → puntaje 0-100 algo indulgente (acento leve ≠ error)."""
    return float(100 * min(1.0, (p / 0.6)) ** 0.8)


# --------------------------------------------------------------------------
# Evaluación
# --------------------------------------------------------------------------

def assess(samples: np.ndarray, text: str, lang: str) -> dict:
    """Evalúa la pronunciación de `text` en el audio `samples` (16 kHz, float32)."""
    import torch

    if not load():
        raise RuntimeError("motor de fonemas no disponible")

    words = g2p.sentence_phones(text, lang)
    flat: list[tuple[int, int, str]] = []   # (índice palabra, id token, fonema)
    word_tokens: list[list[int]] = []
    optional: set[int] = set()  # fonemas opcionales (liaison francesa)
    for wi, (word, phones) in enumerate(words):
        idxs = []
        liaison = (lang == "fr" and len(phones) > len(g2p.word_phones(word, lang))
                   and phones[-1] in ("z", "t", "n", "p", "ʁ"))
        for pi, p in enumerate(phones):
            for tid in _tokenize_phone(p):
                if liaison and pi == len(phones) - 1:
                    optional.add(len(flat))
                idxs.append(len(flat))
                flat.append((wi, tid, _inv[tid]))
        word_tokens.append(idxs)
    if not flat:
        raise ValueError("No hay palabras que evaluar")

    inputs = _fe(samples, sampling_rate=16000, return_tensors="pt")
    with torch.inference_mode():
        logits = _model(inputs.input_values).logits[0].numpy()
    logp = _log_softmax(logits.astype(np.float64))
    T = logp.shape[0]
    if T < len(flat):
        # Audio demasiado corto para tantos fonemas → casi seguro no se dijo la frase.
        raise ValueError("La grabación es demasiado corta para esa frase")

    probs = np.exp(logp)
    speech_frames = int((probs[:, BLANK] < 0.5).sum())
    if speech_frames < max(3, len(flat) * 0.25):
        raise ValueError("No se detectó voz en la grabación")

    spans = _ctc_force_align(logp, [t for _, t, _ in flat])

    # Posterior normalizado sin blank, por frame.
    nb = probs.copy()
    nb[:, :4] = 0
    nb_sum = nb.sum(axis=1, keepdims=True) + 1e-9
    nb_norm = nb / nb_sum
    speechiness = 1 - probs[:, BLANK]

    alts_map = ALTERNATES.get(lang, {})
    phone_results = []
    for fi, ((wi, tid, ph), (a, b)) in enumerate(zip(flat, spans)):
        # Ampliamos 1 frame a cada lado: los picos CTC son estrechos.
        a2, b2 = max(0, a - 1), min(T - 1, b + 1)
        seg = nb_norm[a2 : b2 + 1]
        w = speechiness[a2 : b2 + 1] + 1e-3
        ok_ids = [tid] + [_vocab[x] for x in alts_map.get(ph, ()) if x in _vocab]
        p_target = float(max((seg[:, i] * w).sum() / w.sum() for i in ok_ids))
        # El mejor frame del segmento también cuenta (un pico claro es buena señal).
        p_peak = float(max(seg[:, i].max() for i in ok_ids))
        p = 0.5 * p_target + 0.5 * p_peak
        avg = (seg * w[:, None]).sum(axis=0) / w.sum()
        heard_id = int(avg.argmax())
        heard = _inv.get(heard_id, "?")
        score = _calibrate(p)
        if fi in optional:
            score, heard_id = max(score, 95.0), tid
        phone_results.append({
            "word_index": wi, "phone": ph, "score": round(score, 1),
            "heard": heard if heard_id not in ok_ids and avg[heard_id] > p_target * 1.3 else None,
            "start": round(a * FRAME_SEC, 2), "end": round((b + 1) * FRAME_SEC, 2),
        })

    word_results = []
    for wi, (word, phones) in enumerate(words):
        prs = [phone_results[i] for i in word_tokens[wi]]
        if prs:
            sc = float(np.mean([p["score"] for p in prs]))
            # Un fonema muy mal hundido en una palabra debe notarse aunque el resto esté bien.
            sc = min(sc, min(p["score"] for p in prs) + 35)
        else:
            sc = 0.0
        word_results.append({
            "word": word,
            "ipa": "".join(phones),
            "score": round(sc, 1),
            "start": prs[0]["start"] if prs else None,
            "end": prs[-1]["end"] if prs else None,
            "phones": [{k: p[k] for k in ("phone", "score", "heard")} for p in prs],
        })

    total = sum(len(word_tokens[i]) for i in range(len(words))) or 1
    overall = sum(w["score"] * len(word_tokens[i]) for i, w in enumerate(word_results)) / total

    # Fluidez: pausas largas entre palabras y velocidad.
    starts = [w["start"] for w in word_results if w["start"] is not None]
    ends = [w["end"] for w in word_results if w["end"] is not None]
    spoken = (ends[-1] - starts[0]) if starts and ends else 0
    pauses = sum(
        1 for i in range(1, len(word_results))
        if word_results[i]["start"] and word_results[i - 1]["end"]
        and word_results[i]["start"] - word_results[i - 1]["end"] > 0.6
    )
    wpm = round(len(word_results) / (spoken / 60)) if spoken > 0.3 else 0

    # Sonidos a mejorar: los fonemas con peor puntaje (sin repetir).
    weak: dict[str, dict] = {}
    for p in sorted(phone_results, key=lambda x: x["score"]):
        if p["score"] >= 70 or p["phone"] in weak:
            continue
        weak[p["phone"]] = {
            **tip_for(lang, p["phone"]),
            "score": p["score"],
            "heard": p["heard"],
            "word": words[p["word_index"]][0],
        }
        if len(weak) >= 4:
            break

    return {
        "engine": "phoneme",
        "score": round(overall, 1),
        "words": word_results,
        "heard_phones": " ".join(_greedy_decode(logp)),
        "expected_ipa": g2p.ipa(text, lang),
        "tips": list(weak.values()),
        "fluency": {"wpm": wpm, "long_pauses": pauses, "duration": round(spoken, 2)},
        "phone_scores": [(p["phone"], p["score"]) for p in phone_results],
    }
