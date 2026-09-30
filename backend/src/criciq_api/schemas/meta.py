"""Response models for service metadata endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    version: str


class Meta(BaseModel):
    api_version: Literal["v1"]
    app_version: str
    data_version: str | None
    """Version of the loaded serving dataset; ``None`` until a dataset is loaded (M2)."""
    model_versions: dict[str, str]
    """Loaded model name -> semantic version; empty until models ship (M3+)."""
