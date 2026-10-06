from __future__ import annotations

from fastapi import APIRouter

from criciq_api.api.v2.routers import players

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(players.router)
