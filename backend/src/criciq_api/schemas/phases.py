"""Response models for Phase Analysis: how innings are built, phase by phase."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.common import Coverage
from criciq_api.schemas.players import TeamTag


class PhaseFilters(BaseModel):
    """The filters applied (all optional), echoed back."""

    season_from: int | None = None
    season_to: int | None = None
    team: str | None = Field(
        default=None,
        description="A franchise id: its batting in the phase cards and overs, its own players "
        "in the leaders, its matches in the results and toss.",
    )
    venue: str | None = Field(default=None, description="A venue id.")
    innings: int | None = Field(
        default=None, description="1 batting first, 2 chasing (Tests: the innings, 1 to 4)."
    )
    min_balls: int = Field(description="Balls a player needs in a phase to be a leader.")


class PhaseSummary(BaseModel):
    key: str
    label: str
    first_over: int
    last_over: int | None = Field(description="None: open-ended (a Test's last phase).")
    innings: int = Field(description="Innings that reached the phase.")
    runs: int
    balls: int = Field(description="Legal balls.")
    wickets: int
    fours: int
    sixes: int
    dots: int
    run_rate: float | None
    runs_per_innings: float | None
    wickets_per_innings: float | None
    boundary_pct: float | None = Field(description="Fours and sixes per 100 legal balls.")
    dot_pct: float | None
    balls_per_wicket: float | None


class OverPoint(BaseModel):
    """One over (or, in Tests, a block of ten overs)."""

    first_over: int
    last_over: int
    label: str
    phase: str
    innings: int = Field(description="Innings that reached it.")
    runs: int
    balls: int
    wickets: int
    run_rate: float | None
    wickets_per_over: float | None


class SideRecord(BaseModel):
    matches: int
    won: int
    drawn: int = Field(description="Tests only.")
    win_pct: float | None


class ResultSplit(BaseModel):
    """Results by who batted first. A tie settled by a super over counts for its winner;
    no results are left out."""

    matches: int
    batting_first: SideRecord
    chasing: SideRecord = Field(description="Batting second (in Tests, the side that did).")
    first_innings_average: float | None
    average_total_defended: float | None = Field(
        description="First-innings total in matches the side batting first won (limited overs)."
    )


class TossDecision(BaseModel):
    decision: Literal["bat", "field"]
    matches: int
    toss_winner_won: int
    win_pct: float | None


class BattingLeader(BaseModel):
    rank: int
    tied: bool
    player_id: str
    name: str
    team: TeamTag | None
    innings: int
    balls: int
    runs: int
    outs: int
    strike_rate: float | None
    average: float | None
    boundary_pct: float | None
    dot_pct: float | None


class BowlingLeader(BaseModel):
    rank: int
    tied: bool
    player_id: str
    name: str
    team: TeamTag | None
    innings: int
    balls: int
    runs: int
    wickets: int
    economy: float | None
    strike_rate: float | None = Field(description="Balls per wicket.")
    average: float | None
    dot_pct: float | None
    boundary_pct: float | None = Field(description="Fours and sixes conceded per 100 balls.")


class PhaseLeaders(BaseModel):
    phase: str
    batters: list[BattingLeader] = Field(description="Most runs, then fewest balls.")
    bowlers: list[BowlingLeader] = Field(description="Most wickets, then lowest economy.")


class GroundPhase(BaseModel):
    phase: str
    balls: int
    run_rate: float | None


class GroundPhases(BaseModel):
    venue_id: str
    name: str
    city: str | None
    matches: int
    phases: list[GroundPhase]


class PhaseAnalysis(BaseModel):
    coverage: Coverage
    format: Literal["T20", "ODI", "Test"]
    filters: PhaseFilters
    phases: list[PhaseSummary]
    over_block: int = Field(description="Overs per point in `overs`: 1, or 10 in Tests.")
    overs: list[OverPoint]
    results: ResultSplit
    toss: list[TossDecision]
    leaders: list[PhaseLeaders]
    grounds: list[GroundPhases] = Field(
        description="Run rate by phase at the busiest grounds: from the balls bowled there, "
        "not from pitch or weather data."
    )
