"""Texto → fonemas IPA con espeak-ng (incluido vía espeakng-loader, sin instalar nada)."""
from __future__ import annotations

import re
import threading
from functools import lru_cache

import espeakng_loader
from phonemizer.backend import EspeakBackend
from phonemizer.backend.espeak.wrapper import EspeakWrapper
from phonemizer.separator import Separator

from .config import LANGUAGES

EspeakWrapper.set_library(espeakng_loader.get_library_path())
EspeakWrapper.set_data_path(espeakng_loader.get_data_path())

_backends: dict[str, EspeakBackend] = {}
_lock = threading.Lock()
_SEP = Separator(phone=" ", word=" | ", syllable="")

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)*")


def _backend(lang: str) -> EspeakBackend:
    code = LANGUAGES.get(lang, LANGUAGES["en"])["espeak"]
    if code not in _backends:
        _backends[code] = EspeakBackend(
            code, preserve_punctuation=False, with_stress=False, language_switch="remove-flags"
        )
    return _backends[code]


def words_of(text: str) -> list[str]:
    return [w.replace("’", "'") for w in WORD_RE.findall(text)]


@lru_cache(maxsize=20000)
def word_phones(word: str, lang: str) -> tuple[str, ...]:
    with _lock:
        out = _backend(lang).phonemize([word.lower()], separator=_SEP, strip=True)[0]
    return tuple(p for p in out.replace("|", " ").split() if p)


@lru_cache(maxsize=5000)
def _sentence_cached(text: str, lang: str) -> tuple:
    ws = words_of(text)
    # Fonemizar la frase completa da las formas débiles reales ("a" → ə, "the" → ðə),
    # que palabra por palabra saldrían como si estuvieran aisladas ("a" → eɪ).
    with _lock:
        out = _backend(lang).phonemize([" ".join(ws).lower()], separator=_SEP, strip=True)[0]
    chunks = [tuple(p for p in c.split() if p) for c in out.split("|")]
    chunks = [c for c in chunks if c]
    if len(chunks) == len(ws):
        return tuple(zip(ws, chunks))
    # Si espeak unió o separó palabras, volvemos al modo palabra por palabra.
    return tuple((w, word_phones(w, lang)) for w in ws)


def sentence_phones(text: str, lang: str) -> list[tuple[str, tuple[str, ...]]]:
    """[(palabra, (fonemas...)), ...] para cada palabra de la oración."""
    return list(_sentence_cached(text.strip(), lang))


def ipa(text: str, lang: str) -> str:
    return " ".join("".join(p) for _, p in sentence_phones(text, lang))


_display: dict[str, EspeakBackend] = {}


def display_ipa_words(text: str, lang: str) -> list[tuple[str, str]]:
    """Transcripción para MOSTRAR (puede diferir de la usada para puntuar, p. ej. portugués de Brasil)."""
    code = LANGUAGES.get(lang, {}).get("espeak_display")
    if not code:
        return [(w, "".join(p)) for w, p in sentence_phones(text, lang)]
    ws = words_of(text)
    with _lock:
        if code not in _display:
            _display[code] = EspeakBackend(code, preserve_punctuation=False, with_stress=False,
                                           language_switch="remove-flags")
        out = _display[code].phonemize([w.lower() for w in ws], separator=Separator(phone="", word=" "), strip=True)
    return list(zip(ws, out))
