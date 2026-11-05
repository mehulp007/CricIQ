"""Response pieces shared by the analysis pages: coverage, filters and ranked rows."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class Coverage(BaseModel):
    """What the competition's data covers: every figure on a page comes from these matches."""

    first_season: int | None
    last_season: int | None
    first_season_label: str | None = Field(
        description='e.g. "2011/12" where seasons span the new year.'
    )
    last_season_label: str | None
    matches: int
    first_date: dt.date | None
    last_date: dt.date | None


class Filters(BaseModel):
    """The filters a page applied (all optional), echoed back with its results."""

    season_from: int | None = None
    season_to: int | None = None
    team: str | None = Field(
        default=None, description="A franchise id (a team in this competition)."
    )
    opponent: str | None = None
    venue: str | None = Field(default=None, description="A venue id.")
    innings: int | None = Field(default=None, ge=1, le=4)


class RankedRow(BaseModel):
    """A row's place in a ranked table: equal values share a rank ("=3")."""

    rank: int
    tied: bool
    value: float | None
    sample: int | None = Field(
        default=None, description="Innings, balls or matches behind the value."
    )
