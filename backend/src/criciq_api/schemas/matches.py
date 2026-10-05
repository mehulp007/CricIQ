"""Response models for matches, scorecards and replay timelines."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

OutcomeType = Literal["win", "tie", "no_result"]


class TeamRef(BaseModel):
    team_season_id: str
    franchise_id: str
    name: str
    color: str


class TeamScore(TeamRef):
    runs: int | None
    wickets: int | None
    overs: str | None = Field(description="Scoreboard overs, e.g. '19.4'.")


class VenueRef(BaseModel):
    venue_id: str
    name: str
    city: str


class Toss(BaseModel):
    winner_id: str | None
    winner_name: str | None
    decision: Literal["bat", "field"] | None


class MatchSummary(BaseModel):
    match_id: int
    season: int
    date: dt.date
    match_number: int | None
    stage: str
    is_playoff: bool
    venue: VenueRef
    team_a: TeamScore = Field(description="The side that batted first.")
    team_b: TeamScore
    target_runs: int | None
    outcome_type: OutcomeType
    winner_id: str | None
    result_text: str
    win_method: str | None
    decided_by_super_over: bool
    toss: Toss
    player_of_match: list[str]


class MatchPage(BaseModel):
    items: list[MatchSummary]
    total: int
    page: int
    page_size: int


# --------------------------------------------------------------------------- scorecard


class BattingEntry(BaseModel):
    player_id: str
    name: str
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float | None
    dismissal: str | None = Field(description="How out, e.g. 'c Dhoni b Bravo'; None if not out.")
    is_out: bool


class BowlingEntry(BaseModel):
    player_id: str
    name: str
    overs: str
    maidens: int
    runs: int
    wickets: int
    economy: float | None
    wides: int
    noballs: int


class Extras(BaseModel):
    byes: int
    legbyes: int
    wides: int
    noballs: int
    penalty: int
    total: int


class FallOfWicket(BaseModel):
    wicket: int
    runs: int
    overs: str
    player_id: str
    name: str


class PlayerRef(BaseModel):
    player_id: str
    name: str


class InningsScorecard(BaseModel):
    innings_no: int
    is_super_over: bool
    batting_team: TeamRef
    bowling_team: TeamRef
    runs: int
    wickets: int
    overs: str
    target_runs: int | None
    target_overs: float | None
    extras: Extras
    batting: list[BattingEntry]
    did_not_bat: list[PlayerRef]
    bowling: list[BowlingEntry]
    fall_of_wickets: list[FallOfWicket]


class MatchDetail(BaseModel):
    summary: MatchSummary
    innings: list[InningsScorecard]


# --------------------------------------------------------------------------- timeline


class TimelinePlayer(BaseModel):
    name: str
    full_name: str | None


class TimelineInnings(BaseModel):
    innings_no: int
    batting_team_id: str
    bowling_team_id: str
    is_super_over: bool
    target_runs: int | None
    target_balls: int | None
    max_balls: int = Field(description="Legal balls available to the batting side.")
    wp_start: float | None = Field(
        default=None,
        description="Win probability of the side batting first before this innings' first ball.",
    )
    factors_start: list[float] | None = Field(
        default=None, description="Explanation of wp_start (see Timeline.win_probability)."
    )
    projection_start: list[int] | None = Field(
        default=None,
        description="First innings only: quantiles of the final total before the first ball.",
    )
    leverage_start: float | None = Field(
        default=None,
        description="How much the next ball can move the match: expected change in win "
        "probability over the next ball, relative to a typical ball (1 = typical).",
    )
    pressure_start: int | None = Field(
        default=None,
        description="Pressure index for the next ball: percentile of leverage among every "
        "historical IPL ball (0-100).",
    )


class TimelineWicket(BaseModel):
    player_out_id: str
    kind: str
    bowler_credited: bool
    is_dismissal: bool
    fielder_ids: list[str]


class TimelineDelivery(BaseModel):
    innings_no: int
    seq_no: int
    over_no: int = Field(description="0-based over number.")
    ball_label: str | None
    legal_ball_no: int = Field(description="Legal balls bowled in the innings after this delivery.")
    is_legal: bool
    batter_id: str
    non_striker_id: str
    bowler_id: str
    runs_batter: int
    runs_extras: int
    runs_total: int
    wides: int
    noballs: int
    byes: int
    legbyes: int
    penalty: int
    is_four: bool
    is_six: bool
    team_runs: int = Field(description="Innings score after this delivery.")
    team_wickets: int
    wicket: TimelineWicket | None
    wp: float | None = Field(
        default=None,
        description="Win probability of the side batting first after this ball (model estimate).",
    )
    factors: list[float] | None = Field(
        default=None,
        description="Percentage points each factor adds to the batting side's chance, relative "
        "to the model's average, in the order of Timeline.win_probability.factor_keys. "
        "Absent once the result is certain.",
    )
    projection: list[int] | None = Field(
        default=None,
        description="First innings only: quantiles of the final total after this ball, at the "
        "levels in Timeline.score_projection.levels (model estimate).",
    )
    leverage: float | None = Field(
        default=None,
        description="How much the next ball can move the match: expected change in win "
        "probability over the next ball, relative to a typical ball (1 = typical).",
    )
    pressure: int | None = Field(
        default=None,
        description="Pressure index for the next ball: percentile of leverage among every "
        "historical IPL ball (0-100).",
    )
    momentum: float | None = Field(
        default=None,
        description="Change in the batting side's win probability over the last 12 legal "
        "balls, in percentage points.",
    )


class TimelineSubstitution(BaseModel):
    innings_no: int
    seq_no: int
    team_season_id: str
    player_in_id: str | None
    player_out_id: str | None
    reason: str | None


class WinProbabilityModel(BaseModel):
    """The model behind a timeline's win probabilities."""

    version: str
    trained_from: int
    trained_through: int
    factor_keys: list[str] = Field(description="Order of the values in each `factors` list.")
    base_innings1: float = Field(
        description="Average first-innings estimate: the reference point for its factors."
    )
    base_innings2: float = Field(
        description="Average chase estimate: the reference point for its factors."
    )
    pressure_thresholds: list[float] | None = Field(
        default=None,
        description="Leverage at the pressure index's band edges (50, 80 and 95): where Medium, "
        "High and Very high pressure begin.",
    )


class ScoreProjectionModel(BaseModel):
    """The model behind a timeline's first-innings score projections."""

    version: str
    trained_from: int
    trained_through: int
    levels: list[float] = Field(description="Quantile level of each value in `projection`.")


class Timeline(BaseModel):
    """Everything the client needs to replay a match ball by ball, in one payload."""

    summary: MatchSummary
    teams: dict[str, TeamRef]
    players: dict[str, TimelinePlayer]
    innings: list[TimelineInnings]
    deliveries: list[TimelineDelivery]
    substitutions: list[TimelineSubstitution]
    win_probability: WinProbabilityModel | None = Field(
        default=None, description="Present when the match has model win probabilities."
    )
    score_projection: ScoreProjectionModel | None = Field(
        default=None, description="Present when the first innings has score projections."
    )
