"""FastAPI application factory.

Run locally with ``just dev-api`` (uvicorn with reload).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from criciq_api import __version__
from criciq_api.api.v1.router import api_router
from criciq_api.core.config import Settings, get_settings
from criciq_api.schemas.meta import Health


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="CricIQ API",
        version=__version__,
        description="Cricket intelligence, ball by ball. Model outputs are estimates, "
        "not guarantees of real outcomes.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["meta"])
    def healthz() -> Health:
        return Health(status="ok", version=__version__)

    app.include_router(api_router)
    return app


app = create_app()
