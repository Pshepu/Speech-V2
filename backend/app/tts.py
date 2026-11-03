"""Texto a voz con las voces neuronales de Microsoft Edge (edge-tts, sin API key).

El audio se guarda en disco (data/tts_cache) para no volver a sintetizarlo.
"""
from __future__ import annotations

import hashlib
import random

import edge_tts

from .config import LANGUAGES, TTS_CACHE_DIR


def pick_voice(lang: str, voice: str | None = None, random_voice: bool = False) -> str:
    info = LANGUAGES.get(lang, LANGUAGES["en"])
    if voice and voice in info["voices"]:
        return voice
    if random_voice:
        return random.choice(info["voices"])
    return info["tts_default"]


async def synthesize(text: str, lang: str = "en", voice: str | None = None,
                     rate: int = 0, random_voice: bool = False) -> tuple[bytes, str]:
    """Devuelve (mp3, voz usada). rate en %, p. ej. -30 para audio lento."""
    v = pick_voice(lang, voice, random_voice)
    rate_str = f"{'+' if rate >= 0 else ''}{int(rate)}%"
    key = hashlib.sha1(f"{v}|{rate_str}|{text}".encode()).hexdigest()
    path = TTS_CACHE_DIR / f"{key}.mp3"
    if path.exists():
        return path.read_bytes(), v
    comm = edge_tts.Communicate(text, v, rate=rate_str)
    chunks = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            chunks.extend(chunk["data"])
    data = bytes(chunks)
    if data:
        path.write_bytes(data)
    return data, v
