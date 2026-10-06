"""Response models for service metadata endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    version: str


class SeasonInfo(BaseModel):
    year: int
    matches: int
    impact_player_rule: bool


class FranchiseInfo(BaseModel):
    franchise_id: str
    name: str
    primary_color: str
    secondary_color: str
    first_season: int
    last_season: int | None
    is_active: bool


class VenueInfo(BaseModel):
    venue_id: str
    name: str
    city: str
    country: str
    matches: int


class Meta(BaseModel):
    api_version: Literal["v1"]
    app_version: str
    data_version: str
    """Version of the loaded serving dataset (latest match date + content hash)."""
    model_versions: dict[str, str]
    """Model name -> semantic version of the models that scored this data."""
    seasons: list[SeasonInfo]
    franchises: list[FranchiseInfo]
    venues: list[VenueInfo]
