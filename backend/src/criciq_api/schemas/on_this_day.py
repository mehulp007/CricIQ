"""Response models for On This Day: the matches played on a calendar date in past years."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.players import TeamTag


class DayPerformance(BaseModel):
    """A match's best innings or best bowling."""

    kind: Literal["batting", "bowling"]
    player_id: str
    name: str
    team: TeamTag | None
    figure: str = Field(description='"101*" or "5/33".')
    detail: str = Field(description='"off 121 balls" or "in 10 overs".')
    against: str | None


class DaySwing(BaseModel):
    """The match's biggest change in win probability from one ball (a model estimate)."""

    ball: str = Field(description='The replay ball, "innings.seq".')
    team: TeamTag | None = Field(description="The side whose chance rose.")
    before: float = Field(description="Its chance before the ball, in percent.")
    after: float
    swing: float = Field(description="Percentage points.")


class DayEntry(BaseModel):
    match_id: int
    date: dt.date
    year: int
    season: int
    stage: str
    is_playoff: bool
    teams: list[TeamTag]
    venue: str | None
    result: str
    headline: str = Field(description='e.g. "Virat Kohli: 101* against South Africa".')
    highlight: DayPerformance | None = Field(description="The performance the headline names.")
    batting: DayPerformance | None
    bowling: DayPerformance | None
    player_of_match: list[str]
    swing: DaySwing | None
    notability: int = Field(
        description="How much the entry stands out: finals and playoffs, hundreds, five-fors "
        "and big swings."
    )


class OnThisDay(BaseModel):
    month: int
    day: int
    entries: list[DayEntry] = Field(description="Most notable first, then the most recent.")
