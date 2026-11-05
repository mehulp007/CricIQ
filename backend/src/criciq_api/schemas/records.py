"""Response models for the Records hub: every record list, its leader and its entries."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.common import Coverage
from criciq_api.schemas.players import TeamTag

RecordGroup = Literal[
    "batting", "bowling", "fielding", "seasons", "partnerships", "teams", "ball_by_ball"
]


class RecordPlayer(BaseModel):
    player_id: str
    name: str
    role: Literal["batter", "bowler"] | None = Field(
        default=None, description="What they were doing (a swing's batter and bowler)."
    )


class RecordFigure(BaseModel):
    """One figure beside the value (innings, average, balls...)."""

    label: str
    value: str


class RecordEntry(BaseModel):
    rank: int
    tied: bool = Field(description="Shares its rank with another entry.")
    value: float
    display: str = Field(description='The figure as written, e.g. "175", "75*", "6/12", "9,336".')
    players: list[RecordPlayer] = Field(description="The player, or a stand's two batters.")
    team: TeamTag | None
    opponent: TeamTag | None
    venue: str | None
    match_id: int | None
    date: dt.date | None
    season: int | None
    ball: str | None = Field(description='The replay ball to open, "innings.seq".')
    figures: list[RecordFigure]


class RecordInfo(BaseModel):
    key: str
    group: RecordGroup
    label: str
    level: Literal["career", "innings", "match", "season", "stand", "over"]
    ascending: bool = Field(description="Lower is better (averages, economy, fastest).")
    unit: str
    description: str
    qualification: str | None = Field(description='e.g. "At least 20 innings".')
    model: bool = Field(description="Built from a model's estimates.")
    columns: list[str] = Field(description="The headers of each entry's `figures`.")


class RecordLeader(BaseModel):
    record: RecordInfo
    leaders: list[RecordEntry] = Field(description="The top entry, and any it ties with (up to 3).")
    tied_count: int = Field(description="Entries sharing first place.")


class RecordsHub(BaseModel):
    coverage: Coverage
    format: Literal["T20", "ODI", "Test"]
    groups: list[RecordGroup]
    records: list[RecordLeader]


class RecordFilters(BaseModel):
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None
    opponent: str | None = None
    venue: str | None = None
    wicket: int | None = Field(default=None, description="Partnerships only.")


class RecordList(BaseModel):
    coverage: Coverage
    format: Literal["T20", "ODI", "Test"]
    record: RecordInfo
    filters: RecordFilters
    total: int = Field(description="Entries in the whole list.")
    offset: int
    entries: list[RecordEntry]
