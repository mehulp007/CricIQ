"""Response models for the Player Lab: directory, profiles and splits.

"Par" fields are what an average IPL player would have produced from the same
balls (league rate for the same season and phase). They put numbers from
different eras and roles on the same footing.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["batter", "bowler", "all_rounder"]
Result = Literal["won", "lost", "no_result"]
RatingUnit = Literal[
    "runs_per_100",
    "dismissals_per_100",
    "runs_per_over",
    "wickets_per_4_overs",
    "points",
    "percent",
]
Stability = Literal["high", "moderate", "low"]


class TeamTag(BaseModel):
    franchise_id: str
    name: str
    color: str


class TeamStint(TeamTag):
    seasons: list[int]
    matches: int


class SeasonWindow(BaseModel):
    first: int = Field(description="First season included.")
    last: int = Field(description="Last season included.")


# --------------------------------------------------------------------------- directory


class PlayerListItem(BaseModel):
    player_id: str
    name: str
    full_name: str | None
    country: str | None
    role: Role
    is_keeper: bool
    team: TeamTag | None = Field(description="Most recent team within the filters.")
    first_season: int = Field(description="Career debut season.")
    last_season: int = Field(description="Most recent season played.")
    matches: int = Field(description="Matches within the filters.")
    runs: int
    batting_average: float | None
    strike_rate: float | None
    wickets: int
    economy: float | None


class PlayerPage(BaseModel):
    items: list[PlayerListItem]
    total: int
    page: int
    page_size: int


# --------------------------------------------------------------------------- profile


class PlayerBio(BaseModel):
    player_id: str
    name: str
    full_name: str | None
    country: str | None
    date_of_birth: dt.date | None
    batting_hand: Literal["right", "left"] | None
    bowling_arm: Literal["right", "left"] | None
    bowling_type: Literal["pace", "spin"] | None
    bowling_style: str | None
    role: Role
    is_keeper: bool
    first_season: int
    last_season: int
    matches: int
    teams: list[TeamStint] = Field(description="Franchises played for, most recent first.")


class HighScore(BaseModel):
    runs: int
    not_out: bool
    match_id: int
    season: int
    opposition_id: str


class BestFigures(BaseModel):
    wickets: int
    runs: int
    match_id: int
    season: int
    opposition_id: str


class BattingSummary(BaseModel):
    matches: int
    innings: int
    not_outs: int
    runs: int
    balls: int
    outs: int
    average: float | None
    strike_rate: float | None
    highest: HighScore | None
    fifties: int
    hundreds: int
    ducks: int
    fours: int
    sixes: int
    dot_pct: float | None
    boundary_pct: float | None
    par_strike_rate: float | None
    par_average: float | None
    par_dot_pct: float | None
    par_boundary_pct: float | None
    runs_above_par: float = Field(description="Runs scored minus par runs for the same balls.")
    wpa: float | None = Field(description="Win probability added, in probability units.")
    wpa_innings: int = Field(description="Innings with win probabilities behind ``wpa``.")


class BowlingSummary(BaseModel):
    matches: int
    innings: int
    balls: int
    overs: str
    runs: int
    wickets: int
    average: float | None
    economy: float | None
    strike_rate: float | None
    best: BestFigures | None
    four_wickets: int = Field(description="Innings with exactly four wickets.")
    five_wickets: int = Field(description="Innings with five or more wickets.")
    maidens: int
    dot_pct: float | None
    boundary_pct: float | None
    wides: int
    noballs: int
    par_economy: float | None
    par_strike_rate: float | None
    par_dot_pct: float | None
    runs_saved: float = Field(description="Par runs minus runs conceded for the same balls.")
    wpa: float | None
    wpa_innings: int


class FieldingSummary(BaseModel):
    catches: int
    stumpings: int
    run_outs: int


class SeasonBatting(BaseModel):
    innings: int
    runs: int
    balls: int
    outs: int
    average: float | None
    strike_rate: float | None
    par_strike_rate: float | None
    highest: int
    fifties: int
    hundreds: int


class SeasonBowling(BaseModel):
    innings: int
    balls: int
    runs: int
    wickets: int
    average: float | None
    economy: float | None
    par_economy: float | None
    strike_rate: float | None


class SeasonLine(BaseModel):
    season: int
    teams: list[str]
    matches: int
    batting: SeasonBatting | None
    bowling: SeasonBowling | None


class PhaseBatting(BaseModel):
    phase: str
    label: str
    balls: int
    runs: int
    outs: int
    strike_rate: float | None
    average: float | None
    dot_pct: float | None
    boundary_pct: float | None
    par_strike_rate: float | None
    par_dot_pct: float | None
    par_boundary_pct: float | None
    share: float = Field(description="Share of the player's balls in this phase (0-1).")


class PhaseBowling(BaseModel):
    phase: str
    label: str
    balls: int
    runs: int
    wickets: int
    economy: float | None
    average: float | None
    strike_rate: float | None
    dot_pct: float | None
    par_economy: float | None
    par_dot_pct: float | None
    share: float


class PhaseSplits(BaseModel):
    batting: list[PhaseBatting]
    bowling: list[PhaseBowling]


class Rating(BaseModel):
    """One CricIQ Rating: a percentile among qualified players, after shrinkage."""

    key: str
    label: str
    description: str
    rating: int | None = Field(
        description="0-100: share of qualified players in the window with a lower estimate. "
        "None below the minimum sample."
    )
    low: int | None = Field(description="Lower end of the 90% interval of the rating.")
    high: int | None = Field(description="Upper end of the 90% interval of the rating.")
    value: float | None = Field(description="Shrunk estimate, in ``unit`` (higher is better).")
    raw: float | None = Field(description="The player's own record, in ``unit``.")
    average: float | None = Field(description="Qualified players' average, in ``unit``.")
    unit: RatingUnit
    exposure: int = Field(description="Balls or innings behind the estimate.")
    exposure_unit: Literal["balls", "innings"]
    weight: float = Field(description="Share of the estimate that comes from the player's record.")
    qualified: bool = Field(description="Whether the player is in the reference population.")
    stability: Stability = Field(
        description="How strongly single-season ratings persist into the next season."
    )


class RatingGroup(BaseModel):
    qualified: bool = Field(description="At least ``min_balls`` in the role in the window.")
    balls: int
    min_balls: int
    population: int = Field(description="Qualified players in the window.")
    items: list[Rating]


class Ratings(BaseModel):
    batting: RatingGroup | None
    bowling: RatingGroup | None


class BattingInnings(BaseModel):
    match_id: int
    season: int
    date: dt.date
    opposition: TeamTag
    venue: str
    position: int
    runs: int
    balls: int
    fours: int
    sixes: int
    is_out: bool
    dismissal: str | None
    result: Result
    wpa: float | None


class BowlingInnings(BaseModel):
    match_id: int
    season: int
    date: dt.date
    opposition: TeamTag
    venue: str
    balls: int
    overs: str
    runs: int
    wickets: int
    economy: float | None
    result: Result
    wpa: float | None


class RecentInnings(BaseModel):
    batting: list[BattingInnings]
    bowling: list[BowlingInnings]


class DismissalCount(BaseModel):
    kind: str
    count: int


class Dismissals(BaseModel):
    batting: list[DismissalCount] = Field(description="How the player got out.")
    bowling: list[DismissalCount] = Field(description="How the player took wickets.")


class PlayerProfile(BaseModel):
    player: PlayerBio
    window: SeasonWindow
    batting: BattingSummary | None
    bowling: BowlingSummary | None
    fielding: FieldingSummary
    seasons: list[SeasonLine]
    phases: PhaseSplits
    ratings: Ratings
    recent: RecentInnings
    dismissals: Dismissals


# --------------------------------------------------------------------------- splits


class BattingSplitRow(BaseModel):
    key: str
    label: str
    color: str | None = None
    innings: int | None = Field(description="None for ball-level splits (phase, bowler type).")
    balls: int
    runs: int
    outs: int
    average: float | None
    strike_rate: float | None
    par_strike_rate: float | None
    dot_pct: float | None
    boundary_pct: float | None
    fifties: int | None
    highest: int | None


class BowlingSplitRow(BaseModel):
    key: str
    label: str
    color: str | None = None
    innings: int | None
    balls: int
    runs: int
    wickets: int
    economy: float | None
    average: float | None
    strike_rate: float | None
    par_economy: float | None
    dot_pct: float | None


class BattingSplitGroup(BaseModel):
    key: str
    label: str
    rows: list[BattingSplitRow]


class BowlingSplitGroup(BaseModel):
    key: str
    label: str
    rows: list[BowlingSplitRow]


class PlayerSplits(BaseModel):
    window: SeasonWindow
    batting: list[BattingSplitGroup]
    bowling: list[BowlingSplitGroup]


# --------------------------------------------------------------------------- similar players


class SimilarPlayer(BaseModel):
    player_id: str
    name: str
    role: Role
    team: TeamTag | None = Field(description="Most recent team.")
    similarity: float = Field(description="Cosine similarity of the two style profiles (-1 to 1).")
    balls: int = Field(description="The player's balls in the role in the window.")
    shared: list[str] = Field(description="Style traits both players share.")


class StyleGroup(BaseModel):
    traits: list[str] = Field(description="The player's most distinctive traits.")
    population: int = Field(description="Players compared (at least the minimum balls).")
    min_balls: int
    items: list[SimilarPlayer]


class SimilarPlayers(BaseModel):
    window: SeasonWindow
    batting: StyleGroup | None
    bowling: StyleGroup | None
