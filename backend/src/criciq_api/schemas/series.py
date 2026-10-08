"""Response models for series and tournaments (Tests, ODIs and T20Is)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.matches import MatchSummary, SeriesRef

__all__ = ["SeriesRef"]


class SeriesTeam(BaseModel):
    franchise_id: str
    name: str
    color: str
    wins: int


class SeriesSummary(BaseModel):
    event_id: str = Field(description='Path segment, e.g. "2005-the-ashes".')
    name: str
    season: str = Field(
        description='"2005", or "2020/21" across the new year; a tournament by '
        "the year of its final."
    )
    kind: Literal["series", "tournament"] = Field(
        description="A series is between two sides, a tournament between more."
    )
    tournament_id: str | None = Field(
        description="The major tournament (cricket-world-cup, t20-world-cup, ...), if one."
    )
    named: bool = Field(
        description="False where Cricsheet names no event: the matches of one pair of sides "
        "within a few weeks are grouped together."
    )
    start_date: dt.date
    end_date: dt.date
    matches: int
    missing: int = Field(
        description="Matches the series' numbering shows are not in the data (often abandoned "
        "without a ball bowled)."
    )
    teams: list[SeriesTeam] = Field(description="Most wins first.")
    drawn: int
    tied: int = Field(description="Ties without a winner.")
    no_result: int
    champion: SeriesTeam | None = Field(description="The winner of the final, when in the data.")
    runner_up: SeriesTeam | None
    recent: bool = Field(
        description="The last match is within two weeks of the data's date: more may follow."
    )
    result_text: str


class SeriesPage(BaseModel):
    items: list[SeriesSummary]
    total: int
    page: int
    page_size: int
    years: list[int] = Field(description="Years with a series or tournament, newest first.")


class SeriesStanding(BaseModel):
    position: int
    team: SeriesTeam
    played: int
    won: int
    lost: int
    tied: int
    no_result: int
    points: int
    nrr: float | None


class SeriesRound(BaseModel):
    name: str
    knockout: bool
    standings: list[SeriesStanding] = Field(description="Empty for the knockouts.")
    matches: list[MatchSummary]


class SeriesMatch(BaseModel):
    summary: MatchSummary
    round: str | None
    winner_low: float | None = Field(
        description="The winner's lowest chance of winning during the match (a comeback when low)."
    )


class SeriesBatter(BaseModel):
    player_id: str
    name: str
    team: str
    innings: int
    runs: int
    balls: int
    outs: int
    high: int
    high_not_out: bool
    hundreds: int
    fifties: int


class SeriesBowler(BaseModel):
    player_id: str
    name: str
    team: str
    innings: int
    balls: int
    runs: int
    wickets: int
    best_wickets: int
    best_runs: int


class DecisivePlayer(BaseModel):
    player_id: str
    name: str
    team: str
    matches: int
    added: float = Field(
        description="Win probability added over the event (in Tests, expected result added: a "
        "win counts one and a draw a half), in matches won."
    )


class SeriesDetail(BaseModel):
    summary: SeriesSummary
    matches: list[SeriesMatch] = Field(description="In order of play.")
    rounds: list[SeriesRound] = Field(description="A tournament's groups and knockouts, in order.")
    batters: list[SeriesBatter]
    bowlers: list[SeriesBowler]
    decisive: list[DecisivePlayer] = Field(description="Most win probability added, both ways.")


class SeriesRecord(BaseModel):
    """Two sides' series against each other."""

    played: int
    a_won: int
    b_won: int
    drawn: int = Field(description="Level series, and series of no result.")
    series: list[SeriesSummary]
