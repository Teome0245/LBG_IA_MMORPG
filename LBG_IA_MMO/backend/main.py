import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.health import router as health_router
from api.v1.router import router as v1_router


def _parse_cors_origins() -> list[str]:
    """Liste d'origines autorisées (pilot servi depuis une autre machine, ex. VM 110). Variable LBG_CORS_ORIGINS : URLs séparées par des virgules."""
    raw = os.environ.get("LBG_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def create_app() -> FastAPI:
    application = FastAPI(title="LBG_IA_MMO Backend", version="0.1.0")

    cors_origins = _parse_cors_origins()
    if cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(health_router)
    application.include_router(v1_router, prefix="/v1")

    pilot_dir = Path(__file__).resolve().parent.parent / "pilot_web"
    if pilot_dir.is_dir():
        application.mount("/pilot", StaticFiles(directory=str(pilot_dir), html=True), name="pilot")

    return application


app = create_app()
