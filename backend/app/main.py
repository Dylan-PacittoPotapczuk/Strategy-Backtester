"""FastAPI entrypoint — API plus optional built React static UI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(
    title="Strategy Backtester",
    description="Historical equity/ETF backtester with risk guardrails",
    version="0.2.0",
)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_extra = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
_origins = _default_origins + _extra
# Same-origin Docker / Render deploy: allow all when serving the SPA from this app.
if os.environ.get("SERVE_FRONTEND", "").lower() in ("1", "true", "yes"):
    _origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

_static_env = os.environ.get("STATIC_DIR", "").strip()
_serve_frontend = os.environ.get("SERVE_FRONTEND", "").lower() in ("1", "true", "yes")
_candidates: list[Path | None] = [Path(_static_env) if _static_env else None]
if _serve_frontend:
    _candidates.extend(
        [
            Path(__file__).resolve().parent.parent / "static",
            Path(__file__).resolve().parents[2] / "frontend" / "dist",
        ]
    )
STATIC_DIR: Path | None = next((p for p in _candidates if p and p.is_dir()), None)


@app.get("/")
def root():
    if STATIC_DIR is not None:
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
    return {
        "name": "Strategy Backtester",
        "version": app.version,
        "docs": "/docs",
        "ui": "Set STATIC_DIR or build frontend/dist to serve the React app from this process.",
    }


if STATIC_DIR is not None:
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """SPA client routes — never shadow /api or /docs."""
        if full_path.startswith("api") or full_path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(404, "Not found")
        # Prefer an exact static file (favicon, robots, etc.)
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(404, "Not found")
