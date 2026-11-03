# Speech V2 — Entrenador personal de idiomas

Aplicación local para aprender **inglés** y **francés** (la interfaz está en español). Combina las técnicas con más respaldo en la investigación sobre adquisición de idiomas, y añade **misiones de inmersión**: juegos de rol con personajes, inspirados en el entrenamiento militar de idiomas.

> Evolución de [huytd/speech](https://github.com/huytd/speech) y de mi versión anterior en Rust (`../speech`). Esta versión está reescrita desde cero en Python + Vue.

## Qué incluye

| Módulo | Qué hace |
|---|---|
| 🏠 **Hoy** | Plan diario automático (repaso, pronunciación, oído, gramática, misión, lectura, fluidez), adaptado a tus puntos débiles. Racha, XP y objetivo de minutos. |
| 🎯 **Misiones** | Campañas *Operación Londres* (13 misiones, A1→B2) y *Opération Paris* (10). Cada una trae un informe previo, un personaje con información que debes conseguir, giros inesperados y un informe final (AAR) con tus errores. Modo **Entrenamiento** (pistas, traducciones, correcciones en vivo) o **Inmersión total**. También hay conversación libre y misiones generadas por IA a tu medida. |
| 🎙️ **Pronunciación** | Evaluación **por fonema** con un modelo wav2vec2 de fonemas y alineación forzada: te dice qué sonido produjiste en lugar del correcto (por ejemplo, oyó /d/ en vez de /ð/). Consejos para hispanohablantes, pares mínimos, shadowing, audio lento y otros acentos. Registra tus sonidos débiles. |
| 👂 **Oído** | Pares mínimos con voces y acentos aleatorios (entrenamiento fonético de alta variabilidad) y dictado. |
| 🧠 **Repaso** | Repetición espaciada con **FSRS** (el algoritmo actual de Anki). Tarjetas de palabras, frases (en dirección de producción) y **tus propios errores**, que se crean solos a partir de misiones, escritura y ejercicios. |
| 📐 **Gramática** | 30 lecciones de inglés y 21 de francés (A1→B2), con explicación en español, errores típicos de hispanohablantes y 10 ejercicios cada una (elegir, completar, ordenar, corregir, traducir). Ejercicios extra ilimitados con IA, cuaderno de errores y escritura libre corregida. |
| 📖 **Lectura** | Historias generadas a tu nivel (input comprensible) con audio. Tocas una palabra para traducirla y guardarla, y luego respondes preguntas de comprensión. |
| 📚 **Vocabulario** | Las ~2.400 palabras más frecuentes de cada idioma, con traducción, ejemplo y audio. |
| ⚡ **Fluidez** | Lectura repetida con palabras por minuto, técnica 4/3/2 y repaso rápido. |
| 📈 **Progreso** | XP por día, sonidos débiles, tipos de error, retención, tiempo por actividad. |

El porqué de cada módulo está en [docs/METODO.md](docs/METODO.md) y dentro de la app, en **🧭 El método**.

## Cómo usarla

Doble clic en **`INICIAR.bat`**. La primera vez:
1. Te pide tu clave gratis de Groq (https://console.groq.com → API Keys).
2. Instala Python y sus dependencias (con `uv`) y compila la interfaz si hace falta.
3. Abre http://localhost:3000.

El modelo de fonemas (~1,2 GB) se descarga solo la primera vez, en `models/`. Mientras tanto, la pronunciación funciona en modo básico (palabra por palabra, con Whisper).

## Arquitectura

```
Speech-V2/
├── backend/            FastAPI (Python 3.13)
│   └── app/
│       ├── main.py         servidor + sirve la web compilada
│       ├── api.py          todas las rutas /api
│       ├── pronunciation.py  wav2vec2 (fonemas) + Viterbi CTC + puntaje por fonema
│       ├── g2p.py          texto → IPA con espeak-ng (incluido, sin instalar nada)
│       ├── phoneme_tips.py consejos por sonido para hispanohablantes
│       ├── missions.py     motor de misiones / conversación / informe AAR
│       ├── srs.py          FSRS
│       ├── planner.py      plan diario, racha, estadísticas
│       ├── llm.py · stt.py · tts.py   Groq (texto y Whisper) y voces de Edge
│       └── db.py           SQLite (data/speech.db)
├── frontend/           Vue 3 + Vite + TypeScript + Pinia
├── content/<idioma>/   contenido fijo: vocab, frases, gramática, misiones, pares mínimos
├── scripts/            generador de contenido (build_content.py) y temario
├── data/               TU progreso (no se versiona)
└── models/             modelos descargados (no se versiona)
```

- **IA de texto**: Groq, `openai/gpt-oss-120b` como modelo principal. Si se alcanza el límite, cambia sola a `qwen3.8-27b` o `gpt-oss-20b`. Sirve cualquier API compatible con OpenAI (ver `.env.example`).
- **Voz a texto**: Whisper `large-v3-turbo` en Groq, con tiempos por palabra.
- **Texto a voz**: voces neuronales de Microsoft Edge (`edge-tts`): 12 voces de inglés y 9 de francés, con distintos acentos. Se guardan en caché en disco.
- **Pronunciación**: `facebook/wav2vec2-lv-60-espeak-cv-ft` en CPU (~1-2 s por frase).

## Desarrollo

```bash
# backend (desde Speech-V2/)
backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 3000
# frontend con recarga en caliente (proxy a :3000)
cd frontend && npm run dev
```

### Regenerar o ampliar el contenido

```bash
backend/.venv/Scripts/python scripts/build_content.py            # todo (reanudable)
backend/.venv/Scripts/python scripts/build_content.py fr grammar # solo una parte
```

El temario de gramática está en `scripts/syllabus.py`. Las misiones y los pares mínimos se escriben a mano en `content/<idioma>/missions.json` y `minimal_pairs.json`. Para añadir un idioma: agrégalo en `backend/app/config.py` (`LANGUAGES`), en `scripts/build_content.py` y en el temario, y escribe su campaña.

## Datos: qué se versiona y qué no

- **Sí** (igual para todos): `content/`, código, scripts.
- **No** (`.gitignore`): `.env` (tu clave), `data/` (tu progreso y caché de audio), `models/`.
