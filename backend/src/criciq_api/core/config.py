"""API settings, read from ``CRICIQ_*`` environment variables."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from criciq_core import paths


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRICIQ_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Also allow Vercel preview deployments of the frontend.
    cors_origin_regex: str | None = r"https://.*\.vercel\.app"
    serving_db: Path = paths.exports_dir() / "serving.duckdb"
    # Historical data only changes on redeploy, so responses are safe to cache.
    cache_max_age: int = 300
    cache_s_maxage: int = 86_400


@cache
def get_settings() -> Settings:
    return Settings()
