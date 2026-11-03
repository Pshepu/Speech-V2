"""Cliente de IA de texto (API compatible con OpenAI; por defecto Groq).

Si el modelo principal llega al límite de uso (HTTP 429) prueba automáticamente
con los modelos de respaldo, para que la app siga funcionando.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from . import config

_client: httpx.AsyncClient | None = None


class LLMError(Exception):
    pass


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15))
    return _client


def available() -> bool:
    return bool(config.LLM_API_KEY)


def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Algunos modelos envuelven el JSON en ```json ... ``` o añaden texto alrededor.
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise LLMError("La IA no devolvió un JSON válido")


async def chat(
    messages: list[dict],
    *,
    json_mode: bool = False,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    fallbacks: bool = True,
) -> Any:
    """Envía mensajes al modelo. Devuelve str, o dict si json_mode=True."""
    if not available():
        raise LLMError("Falta la clave de IA (GROQ_API_KEY) en el archivo .env")

    models = [model or config.LLM_MODEL]
    if fallbacks:
        models += [m for m in config.LLM_FALLBACKS if m not in models]

    last_err = "sin respuesta"
    # Si TODOS los modelos están en su límite por minuto, esperamos lo que indique Groq
    # (retry-after) y reintentamos, en vez de fallar enseguida.
    for round_ in range(3):
        wait = None
        result = await _try_models(models, messages, json_mode, temperature, max_tokens)
        if result[0] == "ok":
            return result[1]
        last_err, wait = result[1], result[2]
        if wait is None or round_ == 2:
            break
        await asyncio.sleep(min(max(wait, 1.0), 25.0))
    raise LLMError(last_err)


async def _try_models(models, messages, json_mode, temperature, max_tokens):
    """Prueba cada modelo. Devuelve ("ok", resultado) o ("err", mensaje, segundos_a_esperar|None)."""
    last_err = "sin respuesta"
    min_wait = None
    all_limited = True
    for m in models:
        for attempt in range(2):
            body: dict[str, Any] = {
                "model": m,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
            }
            if "gpt-oss" in m:
                body["reasoning_effort"] = "low"
            if "qwen3" in m:
                body["reasoning_effort"] = "none"
                # En el plan gratuito Qwen solo permite ~1.000 tokens de salida por minuto.
                # (y cuenta el máximo pedido, no lo usado): pedimos poco para que quepa.
                body["max_completion_tokens"] = min(max_tokens, 600)
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            try:
                r = await client().post(
                    f"{config.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                    json=body,
                )
            except httpx.HTTPError as e:
                last_err = f"error de conexión: {e}"
                await asyncio.sleep(1)
                continue
            if r.status_code == 429:
                last_err = f"{m}: límite de uso alcanzado"
                try:
                    ra = float(r.headers.get("retry-after", "5"))
                except ValueError:
                    ra = 5.0
                # Límite diario (no por minuto): no tiene sentido esperar.
                if "per day" not in r.text and "TPD" not in r.text and "RPD" not in r.text:
                    min_wait = ra if min_wait is None else min(min_wait, ra)
                else:
                    mins = max(1, round(ra / 60))
                    last_err = (f"se agotó el límite DIARIO gratuito de Groq para {m} "
                                f"(se libera poco a poco; prueba en ~{mins} min)")
                break  # pasa al siguiente modelo
            all_limited = False
            if r.status_code == 400 and "reasoning_effort" in r.text:
                # El modelo no soporta ese parámetro: reintenta sin él.
                body.pop("reasoning_effort", None)
                r = await client().post(
                    f"{config.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                    json=body,
                )
            if r.status_code >= 400:
                if "daily" not in last_err and "DIARIO" not in last_err:
                    last_err = f"{m}: HTTP {r.status_code} {r.text[:300]}"
                if r.status_code >= 500 or "json_validate_failed" in r.text:
                    continue  # reintento
                break
            content = r.json()["choices"][0]["message"].get("content") or ""
            if not json_mode:
                return ("ok", content.strip())
            try:
                return ("ok", _extract_json(content))
            except (LLMError, json.JSONDecodeError) as e:
                last_err = f"{m}: {e}"
                continue
    return ("err", last_err, min_wait if all_limited else None)


async def json_call(system: str, user: str, **kw) -> dict:
    return await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True,
        **kw,
    )
