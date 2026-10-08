"""Response models for Team Analytics: franchises, league tables and head-to-head."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.matches import MatchSummary
from criciq_api.schemas.players import SeasonWindow, TeamTag

Finish = Literal["champion", "runner_up", "playoffs", "league"]


class FormerName(BaseModel):
    name: str
    first_season: int
    last_season: int


class Record(BaseModel):
    """Results; a tie settled by a super over counts for the super-over winner."""

    played: int
    won: int
    lost: int
    no_result: int
    drawn: int = Field(default=0, description="Tests only.")
    win_pct: float | None = Field(
        description="Wins as a percentage of matches with a result or drawn (no results left out)."
    )


class Rate(BaseModel):
    """A share of decided matches with a 90% Wilson interval."""

    hits: int
    total: int
    pct: float | None
    low: float | None
    high: float | None


class FranchiseSummary(BaseModel):
    franchise_id: str
    name: str
    color: str
    secondary_color: str
    is_active: bool
    first_season: int
    last_season: int
    seasons: int
    names: list[FormerName] = Field(description="Every name the franchise played under.")
    record: Record
    titles: list[int]
    finals: list[int]
    playoffs: list[int] = Field(description="Seasons in which the side reached the playoffs.")


class SeasonChampion(BaseModel):
    season: int
    champion: TeamTag
    runner_up: TeamTag | None
    final_match_id: int | None
    result_text: str | None


class SeasonTrend(BaseModel):
    season: int
    matches: int = Field(description="Decided matches.")
    chasing_win_pct: float | None
    toss_winner_win_pct: float | None
    field_first_pct: float | None = Field(description="Share of tosses won where the side bowled.")
    home_win_pct: float | None = Field(description="None when the season had no home games.")
    avg_first_innings: float | None


class LeagueTrends(BaseModel):
    chasing: Rate = Field(description="Matches won by the side batting second.")
    toss: Rate = Field(description="Matches won by the side that won the toss.")
    home: Rate = Field(description="Home sides' wins in matches with a home side.")
    close: Rate = Field(description="Close finishes as a share of decided matches.")
    seasons: list[SeasonTrend]


class StandingRow(BaseModel):
    position: int
    team: TeamTag
    team_name: str = Field(description="The name the side played under that season.")
    played: int
    won: int
    lost: int
    no_result: int = Field(description="Includes fixtures abandoned without a ball bowled.")
    points: int
    nrr: float | None
    finish: Finish
    exit_stage: str | None = Field(description="Last playoff match for sides that did not win.")


class Standings(BaseModel):
    season: int
    rows: list[StandingRow]
    playoffs: list[MatchSummary]
    abandoned: int = Field(description="League fixtures abandoned without a ball bowled.")


class TeamsOverview(BaseModel):
    seasons: list[int]
    franchises: list[FranchiseSummary]
    champions: list[SeasonChampion]
    league: LeagueTrends


# --------------------------------------------------------------------------- team profile


class TeamSeason(BaseModel):
    season: int
    team_name: str
    position: int
    teams: int
    played: int
    won: int
    lost: int
    no_result: int
    drawn: int = Field(default=0, description="Tests only.")
    points: int
    nrr: float | None
    finish: Finish
    exit_stage: str | None
    playoff_won: int
    playoff_lost: int


class RecordSplit(BaseModel):
    key: str
    label: str
    record: Record


class RecordGroup(BaseModel):
    key: str
    label: str
    splits: list[RecordSplit]


class PhaseLine(BaseModel):
    balls: int
    runs: int
    wickets: int
    run_rate: float | None
    par_run_rate: float | None = Field(
        description="League run rate in the same seasons and phase, weighted by this side's balls."
    )
    balls_per_wicket: float | None
    par_balls_per_wicket: float | None
    boundary_pct: float | None
    par_boundary_pct: float | None
    dot_pct: float | None
    par_dot_pct: float | None


class TeamPhase(BaseModel):
    phase: str
    label: str
    batting: PhaseLine
    bowling: PhaseLine


class TeamTotal(BaseModel):
    match_id: int
    season: int
    date: dt.date
    opponent: TeamTag
    runs: int
    wickets: int
    overs: str


class TeamMargin(BaseModel):
    match_id: int
    season: int
    date: dt.date
    opponent: TeamTag
    result_text: str


class TeamScoring(BaseModel):
    avg_first_innings: float | None
    first_innings: int
    highest: TeamTotal | None
    lowest: TeamTotal | None = Field(
        description="Lowest completed total (bowled out or all the overs batted)."
    )
    biggest_win_runs: TeamMargin | None
    biggest_win_wickets: TeamMargin | None


class TeamBatter(BaseModel):
    player_id: str
    name: str
    innings: int
    runs: int
    balls: int
    strike_rate: float | None
    average: float | None


class TeamBowler(BaseModel):
    player_id: str
    name: str
    innings: int
    wickets: int
    balls: int
    economy: float | None
    average: float | None


class OpponentRecord(BaseModel):
    opponent: TeamTag
    record: Record


class VenueRecord(BaseModel):
    venue_id: str
    name: str
    city: str
    record: Record


class Swing(BaseModel):
    """A win from a low win probability, or a defeat from a high one."""

    match_id: int
    season: int
    date: dt.date
    opponent: TeamTag
    result_text: str
    win_probability: float = Field(
        description="The side's lowest (comeback) or highest (collapse)."
    )
    innings_no: int
    seq_no: int
    situation: str = Field(description="The score at that ball, e.g. 'CSK 45/4 after 9.2 overs'.")


class TeamProfile(BaseModel):
    team: FranchiseSummary
    window: SeasonWindow
    seasons: list[TeamSeason] = Field(description="Every season, regardless of the window.")
    record: Record
    splits: list[RecordGroup]
    close: Record = Field(description="Close finishes in the window.")
    phases: list[TeamPhase]
    scoring: TeamScoring
    batters: list[TeamBatter]
    bowlers: list[TeamBowler]
    opponents: list[OpponentRecord]
    venues: list[VenueRecord]
    comebacks: list[Swing]
    collapses: list[Swing]


# --------------------------------------------------------------------------- head to head


class H2HRecord(BaseModel):
    played: int
    a_won: int
    b_won: int
    no_result: int
    drawn: int = Field(default=0, description="Tests only.")
    tied: int = Field(description="Ties settled by a super over (already counted as wins).")


class H2HSplit(BaseModel):
    key: str
    label: str
    record: H2HRecord


class H2HSeason(BaseModel):
    season: int
    record: H2HRecord


class H2HExpectation(BaseModel):
    """A's wins against what each side's form in those seasons predicts (log5)."""

    decided: int
    a_won: int
    a_expected: float
    low: float = Field(description="90% range of A's wins from chance alone.")
    high: float
    seasons_used: int


class H2HPlayer(BaseModel):
    player_id: str
    name: str
    team: TeamTag
    innings: int
    runs: int | None = None
    balls: int | None = None
    strike_rate: float | None = None
    wickets: int | None = None
    economy: float | None = None


class H2HScoring(BaseModel):
    a_avg_total: float | None
    b_avg_total: float | None
    a_highest: TeamTotal | None
    b_highest: TeamTotal | None


class TeamHeadToHead(BaseModel):
    a: TeamTag
    b: TeamTag
    window: SeasonWindow
    record: H2HRecord
    expectation: H2HExpectation | None
    splits: list[H2HSplit]
    seasons: list[H2HSeason]
    scoring: H2HScoring
    batters: list[H2HPlayer]
    bowlers: list[H2HPlayer]
    meetings: list[MatchSummary] = Field(description="Every meeting in the window, newest first.")
