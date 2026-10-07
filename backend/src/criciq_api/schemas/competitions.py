"""Response models for /api/v2: the competitions the players database covers and a
player's career in each of them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SeasonLabel(BaseModel):
    year: int = Field(description="The season as the API's season filters take it.")
    label: str = Field(description='How the competition names it: "2023/24" for the BBL.')


class CompetitionScope(BaseModel):
    id: str = Field(description="Path segment for /api/v2/{competition}/..., e.g. bbl or t20.")
    name: str
    short_name: str
    format: Literal["T20", "ODI", "Test"]
    competitions: list[str] = Field(
        description="Competition ids it covers: one, or every T20 competition for t20."
    )
    matches: int
    players: int
    seasons: list[SeasonLabel] = Field(
        description="Seasons played; for t20 the calendar years of every competition."
    )


class CompetitionList(BaseModel):
    data_version: str
    items: list[CompetitionScope]


class CareerLine(BaseModel):
    competition: str = Field(description="The scope's id (path segment).")
    name: str
    matches: int
    first_season: str = Field(description="Season label of the debut.")
    last_season: str = Field(description="Season label of the latest season.")
    runs: int
    batting_average: float | None
    strike_rate: float | None
    par_strike_rate: float | None = Field(
        description="An average batter's strike rate on the same balls in that competition."
    )
    wickets: int
    economy: float | None
    par_economy: float | None


class PlayerCareers(BaseModel):
    player_id: str
    name: str
    full_name: str | None
    country: str | None
    careers: list[CareerLine] = Field(
        description="One line per competition played, with all T20 cricket together after "
        "the T20 competitions."
    )
