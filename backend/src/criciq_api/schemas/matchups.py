"""Response models for the Matchup Lab and next-ball predictions.

Three views of every batter-bowler record:

- ``raw``: what happened, with a sampling interval that shows how little a few
  dozen balls prove.
- ``expected``: what the ball-outcome model predicts for those same balls from
  each player's overall record and the situations they met in.
- ``estimate``: the head-to-head record shrunk towards ``expected``
  (empirical Bayes). History carries weight ``balls / (balls + kappa)``.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from criciq_api.schemas.players import SeasonWindow, TeamTag

Phase = Literal["powerplay", "middle", "death"]
SampleLevel = Literal["none", "tiny", "small", "moderate", "large"]


class Interval(BaseModel):
    value: float | None
    low: float | None = Field(description="Lower end of the 90% interval.")
    high: float | None = Field(description="Upper end; None when unbounded.")


class MatchupNumbers(BaseModel):
    strike_rate: Interval
    balls_per_dismissal: Interval
    dot_pct: Interval
    boundary_pct: Interval


class MatchupPlayer(BaseModel):
    player_id: str
    name: str
    full_name: str | None
    batting_hand: Literal["right", "left"] | None
    bowling_type: Literal["pace", "spin"] | None
    bowling_style: str | None
    team: TeamTag | None


class HeadToHead(BaseModel):
    balls: int
    runs: int
    dismissals: int
    dots: int
    fours: int
    sixes: int
    average: float | None


class SampleSize(BaseModel):
    balls: int
    level: SampleLevel
    weight: float = Field(description="Share of the estimate that comes from head-to-head balls.")
    kappa: float = Field(description="Prior strength, in balls, fitted across all pairs.")


class MatchupSplitRow(BaseModel):
    key: str
    label: str
    balls: int
    runs: int
    dismissals: int
    strike_rate: float | None
    expected_strike_rate: float | None


class MatchupDismissal(BaseModel):
    match_id: int
    season: int
    date: dt.date
    kind: str


class OutcomeProbability(BaseModel):
    outcome: Literal["dot", "one", "two", "three", "four", "six", "out"]
    label: str
    probability: float


class NextBall(BaseModel):
    phase: Phase
    label: str
    model: list[OutcomeProbability] = Field(description="From the players' overall records.")
    with_history: list[OutcomeProbability] = Field(
        description="Adjusted by the shrunk head-to-head record."
    )
    expected_runs: float
    expected_runs_with_history: float


class MatchupDetail(BaseModel):
    batter: MatchupPlayer
    bowler: MatchupPlayer
    window: SeasonWindow
    phase: Phase | None = Field(description="Phase filter applied to the record, if any.")
    head_to_head: HeadToHead
    raw: MatchupNumbers | None
    expected: MatchupNumbers | None
    estimate: MatchupNumbers | None
    sample: SampleSize
    by_phase: list[MatchupSplitRow]
    by_season: list[MatchupSplitRow]
    dismissals: list[MatchupDismissal]
    next_ball: list[NextBall]
    context: str = Field(description="The situation the next-ball probabilities assume.")
    model_version: str | None


class MatchupListItem(BaseModel):
    batter: MatchupPlayer
    bowler: MatchupPlayer
    balls: int
    runs: int
    dismissals: int
    strike_rate: float | None
    expected_strike_rate: float | None
    estimated_strike_rate: float | None
    edge: float | None = Field(
        description="Estimated minus expected strike rate: the matchup effect beyond form."
    )
    weight: float


class MatchupList(BaseModel):
    items: list[MatchupListItem]
    total: int
    kappa: float | None


class NextBallRequest(BaseModel):
    batter_id: str = Field(max_length=32)
    bowler_id: str = Field(max_length=32)
    phase: Phase = "middle"
    innings: Literal[1, 2] = 1
    wickets: int = Field(default=2, ge=0, le=9, description="Wickets down before the ball.")
    batter_balls: int = Field(default=20, ge=0, le=150, description="Balls the batter has faced.")
    pressure: Literal["low", "par", "high", "extreme"] | None = Field(
        default=None, description="Required rate against par; chases only."
    )


class NextBallResponse(BaseModel):
    batter: MatchupPlayer
    bowler: MatchupPlayer
    request: NextBallRequest
    model: list[OutcomeProbability]
    with_history: list[OutcomeProbability]
    expected_runs: float
    expected_runs_with_history: float
    history_balls: int
    model_version: str
