from __future__ import annotations

from fastapi import APIRouter

from criciq_api.api.v1.routers import meta

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meta.router)
