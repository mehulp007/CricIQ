"""FastAPI application factory.

Run locally with ``just dev-api`` (uvicorn with reload).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.concurrency import run_in_threadpool

from criciq_api import __version__
from criciq_api.api.v2.router import api_router
from criciq_api.core.config import Settings, get_settings
from criciq_api.db import Database, serving_paths
from criciq_api.schemas.meta import Health
from criciq_api.services import matches as matches_service
from criciq_api.services import players as players_service
from criciq_api.services import simulation as simulation_service
from criciq_core.publish import pending


def _warm_up(db: Database) -> None:
    """Run each query shape once so the first real request is not slow."""
    latest = db.scalar("SELECT match_id FROM match_summaries ORDER BY match_order DESC LIMIT 1")
    if latest is not None:
        matches_service.get_detail(db, latest)
        matches_service.get_timeline(db, latest)
    if db.has_table("player_index"):
        busiest = db.scalar("SELECT player_id FROM player_index ORDER BY matches DESC LIMIT 1")
        if busiest is not None:
            players_service.get_profile(db, busiest)
            players_service.get_splits(db, busiest)
            players_service.get_similar(db, busiest)
    simulation_service.warm_up(db)


def _data_version(request: Request, players: Database | None) -> str:
    """The data version behind a response (every database shares the sync's)."""
    parts = request.url.path.split("/")
    competition = parts[3] if len(parts) > 3 else "ipl"
    found: Database | None = request.app.state.serving.get(competition)
    source = found or players or request.app.state.serving["ipl"]
    return source.data_version


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One serving database per competition, keyed like the URLs ("ipl", "t20i").
        app.state.serving = {}
        for path in serving_paths(settings.serving_db):
            if path == settings.serving_db or path.exists() or pending(path).exists():
                db = Database(path)
                app.state.serving[(db.competition_id or "IPL").lower()] = db
        # The players database is optional: without it the Player Lab answers 503.
        players = settings.players_db
        app.state.players_db = (
            Database(players) if players.exists() or pending(players).exists() else None
        )
        for db in app.state.serving.values():
            _warm_up(db)
        try:
            yield
        finally:
            for db in app.state.serving.values():
                db.close()
            if app.state.players_db is not None:
                app.state.players_db.close()

    app = FastAPI(
        title="CricIQ API",
        version=__version__,
        description="Cricket intelligence, ball by ball. Model outputs are estimates, "
        "not guarantees of real outcomes.",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def cache_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A sync may have published new data while the API runs (see criciq_api.db).
        for db in request.app.state.serving.values():
            await run_in_threadpool(db.refresh)
        players: Database | None = request.app.state.players_db
        if players is not None:
            await run_in_threadpool(players.refresh)
        response = await call_next(request)
        if request.url.path.startswith("/api/") and request.method == "GET":
            response.headers["X-Data-Version"] = _data_version(request, players)
            if response.status_code == 200:
                response.headers["Cache-Control"] = (
                    f"public, max-age={settings.cache_max_age}, "
                    f"s-maxage={settings.cache_s_maxage}, stale-while-revalidate=604800"
                )
        return response

    @app.get("/healthz", tags=["meta"])
    def healthz() -> Health:
        return Health(status="ok", version=__version__)

    app.include_router(api_router)
    return app


app = create_app()
