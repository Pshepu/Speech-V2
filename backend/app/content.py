"""Carga del contenido fijo (content/<idioma>/*.json). Se recarga si el archivo cambia."""
from __future__ import annotations

import json
import random

from .config import CONTENT_DIR, LANGUAGES

_cache: dict[tuple[str, str], tuple[float, object]] = {}


def _load(lang: str, name: str, default):
    path = CONTENT_DIR / lang / f"{name}.json"
    if not path.exists():
        return default
    mtime = path.stat().st_mtime
    key = (lang, name)
    if key in _cache and _cache[key][0] == mtime:
        return _cache[key][1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[key] = (mtime, data)
    return data


def check_lang(lang: str) -> str:
    return lang if lang in LANGUAGES else "en"


def vocab(lang: str) -> list[dict]:
    return _load(lang, "vocab", [])


def sentences(lang: str) -> list[dict]:
    return _load(lang, "sentences", [])


def _valid_exercise(e: dict) -> bool:
    if e.get("type") == "choice":
        opts = [str(o).strip().lower() for o in e.get("options") or []]
        return len(opts) >= 2 and len(set(opts)) == len(opts)  # sin opciones repetidas
    return True


def grammar(lang: str) -> list[dict]:
    lessons = _load(lang, "grammar", [])
    for l in lessons:
        l["exercises"] = [e for e in l.get("exercises", []) if _valid_exercise(e)]
    return lessons


def lesson(lang: str, lesson_id: str) -> dict | None:
    return next((l for l in grammar(lang) if l["id"] == lesson_id), None)


def packs(lang: str) -> list[dict]:
    return _load(lang, "packs", [])


def minimal_pairs(lang: str) -> list[dict]:
    return _load(lang, "minimal_pairs", [])


def campaigns(lang: str) -> list[dict]:
    return _load(lang, "missions", {"campaigns": []})["campaigns"]


def mission(lang: str, mission_id: str) -> dict | None:
    for c in campaigns(lang):
        for m in c["missions"]:
            if m["id"] == mission_id:
                return m
    return None


def random_sentence(lang: str, level: str | None = None, exclude: set[str] | None = None) -> dict | None:
    pool = [s for s in sentences(lang) if not level or s["level"] == level]
    if exclude:
        pool = [s for s in pool if s["text"] not in exclude] or pool
    return random.choice(pool) if pool else None


FLUENCY_TOPICS = [
    "Describe tu rutina diaria",
    "Habla de tu comida favorita y cómo se prepara",
    "Cuenta tus planes para el próximo fin de semana",
    "Describe el lugar donde vives",
    "Habla de una película o serie que te guste",
    "Describe a tu mejor amigo o amiga",
    "Cuenta qué hiciste el fin de semana pasado",
    "Habla de tu trabajo o tus estudios",
    "Cuenta el mejor viaje que has hecho",
    "Explica por qué quieres aprender este idioma",
    "Describe tu ciudad a alguien que no la conoce",
    "Habla de un problema que resolviste",
]
