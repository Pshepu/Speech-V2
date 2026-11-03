"""Punto de entrada: servidor FastAPI que sirve la API y la web compilada."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, pronunciation
from .api import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Speech V2", version="2.0.0")
app.include_router(router)


@app.on_event("startup")
def startup():
    db.conn()
    # El modelo de fonemas tarda ~15 s en cargar: lo hacemos en segundo plano.
    pronunciation.preload_async()


if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return HTMLResponse("<h1>Speech V2</h1><p>Falta compilar el frontend: <code>cd frontend && npm install && npm run build</code></p>")
