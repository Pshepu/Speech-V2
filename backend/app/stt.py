"""Voz a texto con Whisper (vía Groq). Devuelve texto y tiempos por palabra."""
from __future__ import annotations

from . import config, llm


async def transcribe(wav: bytes, lang: str = "en", prompt: str | None = None) -> dict:
    if not config.LLM_API_KEY:
        raise llm.LLMError("Falta GROQ_API_KEY en .env (necesaria para transcribir)")
    data = {
        "model": config.STT_MODEL,
        "language": config.LANGUAGES.get(lang, {}).get("whisper", lang),
        "response_format": "verbose_json",
        "temperature": "0",
    }
    if prompt:
        data["prompt"] = prompt[:400]
    files = {"file": ("audio.wav", wav, "audio/wav")}
    # timestamp_granularities[] se envía como lista (un campo repetido en el multipart).
    data["timestamp_granularities[]"] = ["word", "segment"]
    r = await llm.client().post(
        f"{config.LLM_BASE_URL}/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        data=data,
        files=files,
    )
    if r.status_code >= 400:
        raise llm.LLMError(f"Whisper HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    words = [
        {"text": w.get("word", "").strip(), "start": w.get("start", 0), "end": w.get("end", 0)}
        for w in (j.get("words") or [])
    ]
    segs = j.get("segments") or []
    # no_speech_prob alto = probablemente no se dijo nada (Whisper a veces "alucina").
    no_speech = max((s.get("no_speech_prob", 0) for s in segs), default=0)
    return {
        "text": (j.get("text") or "").strip(),
        "words": words,
        "duration": j.get("duration"),
        "no_speech": no_speech,
    }
