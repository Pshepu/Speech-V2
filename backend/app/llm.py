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
                break  # pasa al siguiente modelo
            if r.status_code == 400 and "reasoning_effort" in r.text:
                # El modelo no soporta ese parámetro: reintenta sin él.
                body.pop("reasoning_effort", None)
                r = await client().post(
                    f"{config.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                    json=body,
                )
            if r.status_code >= 400:
                last_err = f"{m}: HTTP {r.status_code} {r.text[:300]}"
                if r.status_code >= 500 or "json_validate_failed" in r.text:
                    continue  # reintento
                break
            content = r.json()["choices"][0]["message"].get("content") or ""
            if not json_mode:
                return content.strip()
            try:
                return _extract_json(content)
            except (LLMError, json.JSONDecodeError) as e:
                last_err = f"{m}: {e}"
                continue
    raise LLMError(last_err)


async def json_call(system: str, user: str, **kw) -> dict:
    return await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True,
        **kw,
    )
