"""Response models for service metadata endpoints."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    version: str


class SeasonInfo(BaseModel):
    year: int
    label: str
    """How the season is named: "2023/24" where seasons span the new year, else the year."""
    matches: int
    impact_player_rule: bool


class CompetitionInfo(BaseModel):
    id: str
    """The competition's id in URLs, e.g. ``ipl`` or ``t20i``."""
    name: str
    short_name: str
    format: str
    team_type: Literal["club", "national"]


class Features(BaseModel):
    """What this competition's data supports."""

    win_probability: bool
    score_projection: bool
    ball_model: bool
    simulator: bool
    """False until a simulator version passes its backtest gate here."""


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


class DataUpdate(BaseModel):
    """The latest data sync that changed this competition's matches."""

    updated_at: dt.datetime
    new_matches: int
    corrected_matches: int
    withdrawn_matches: int


class Meta(BaseModel):
    api_version: Literal["v2"]
    app_version: str
    competition: CompetitionInfo
    features: Features
    data_version: str
    """Version of the loaded serving dataset (latest match date + content hash)."""
    model_versions: dict[str, str]
    """Model name -> semantic version of the models that scored this data."""
    latest_match_date: dt.date | None
    """Date of the newest match in the data."""
    last_update: DataUpdate | None
    """The latest sync that brought new, corrected or withdrawn matches (none until one has)."""
    seasons: list[SeasonInfo]
    franchises: list[FranchiseInfo]
    venues: list[VenueInfo]
