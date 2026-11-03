"""Configuración central: rutas, variables de entorno e idiomas soportados."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # carpeta Speech-V2
BACKEND = ROOT / "backend"
CONTENT_DIR = ROOT / "content"
DATA_DIR = ROOT / "data"          # progreso personal (no se versiona)
TTS_CACHE_DIR = DATA_DIR / "tts_cache"
FRONTEND_DIST = ROOT / "frontend" / "dist"
MODELS_DIR = ROOT / "models"

load_dotenv(ROOT / ".env")

# Los modelos de Hugging Face se guardan dentro del proyecto (no en C:).
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

DATA_DIR.mkdir(exist_ok=True)
TTS_CACHE_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "speech.db"

# --- IA (cualquier API compatible con OpenAI; por defecto Groq) ---
LLM_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
# Modelo principal (calidad) y modelos de respaldo si el principal llega al límite.
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_FALLBACKS = [
    m.strip()
    for m in os.getenv("LLM_FALLBACKS", "qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",")
    if m.strip()
]
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "openai/gpt-oss-20b")
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

# Modelo de reconocimiento de fonemas (wav2vec2 CTC entrenado con fonemas de espeak).
PHONEME_MODEL = os.getenv("PHONEME_MODEL", "facebook/wav2vec2-lv-60-espeak-cv-ft")
PHONEME_ENGINE = os.getenv("PHONEME_ENGINE", "auto")  # auto | off

PORT = int(os.getenv("PORT", "3000"))

# --- Idiomas que se pueden aprender (la interfaz está en español) ---
LANGUAGES: dict[str, dict] = {
    "en": {
        "code": "en",
        "name": "Inglés",
        "flag": "🇬🇧",
        "espeak": "en-us",
        "whisper": "en",
        "tts_default": "en-US-AriaNeural",
        # Variedad de voces y acentos: escuchar muchos hablantes distintos mejora la
        # percepción (entrenamiento fonético de alta variabilidad, HVPT).
        "voices": [
            "en-US-AriaNeural", "en-US-GuyNeural", "en-US-JennyNeural", "en-US-ChristopherNeural",
            "en-GB-SoniaNeural", "en-GB-RyanNeural", "en-AU-NatashaNeural", "en-AU-WilliamNeural",
            "en-CA-ClaraNeural", "en-IE-ConnorNeural", "en-IN-NeerjaNeural", "en-NZ-MitchellNeural",
        ],
    },
    "fr": {
        "code": "fr",
        "name": "Francés",
        "flag": "🇫🇷",
        "espeak": "fr-fr",
        "whisper": "fr",
        "tts_default": "fr-FR-DeniseNeural",
        "voices": [
            "fr-FR-DeniseNeural", "fr-FR-HenriNeural", "fr-FR-EloiseNeural",
            "fr-CA-SylvieNeural", "fr-CA-JeanNeural", "fr-BE-CharlineNeural",
            "fr-BE-GerardNeural", "fr-CH-ArianeNeural", "fr-CH-FabriceNeural",
        ],
    },
}

LEVELS = ["A1", "A2", "B1", "B2", "C1"]

# Género de cada voz (para que un personaje femenino no hable con voz masculina).
VOICE_GENDER = {
    "en-US-AriaNeural": "f", "en-US-GuyNeural": "m", "en-US-JennyNeural": "f", "en-US-ChristopherNeural": "m",
    "en-GB-SoniaNeural": "f", "en-GB-RyanNeural": "m", "en-AU-NatashaNeural": "f", "en-AU-WilliamNeural": "m",
    "en-CA-ClaraNeural": "f", "en-IE-ConnorNeural": "m", "en-IN-NeerjaNeural": "f", "en-NZ-MitchellNeural": "m",
    "fr-FR-DeniseNeural": "f", "fr-FR-HenriNeural": "m", "fr-FR-EloiseNeural": "f", "fr-CA-SylvieNeural": "f",
    "fr-CA-JeanNeural": "m", "fr-BE-CharlineNeural": "f", "fr-BE-GerardNeural": "m", "fr-CH-ArianeNeural": "f",
    "fr-CH-FabriceNeural": "m",
}
