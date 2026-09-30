"""API settings, read from ``CRICIQ_*`` environment variables."""

from __future__ import annotations

from functools import cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRICIQ_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:3000"]


@cache
def get_settings() -> Settings:
    return Settings()
