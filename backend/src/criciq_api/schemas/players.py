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


class Percentile(BaseModel):
    key: str
    label: str
    description: str
    value: float | None
    unit: Literal["runs_per_100", "percent", "runs_per_over", "points"]
    higher_is_better: bool
    percentile: int | None = Field(
        description="0-100 among qualified players; None if unqualified."
    )
    balls: int = Field(description="The player's balls behind this metric.")
    min_balls: int
    population: int = Field(description="Qualified players compared against.")


class PercentileGroup(BaseModel):
    qualified: bool
    balls: int
    min_balls: int
    population: int
    items: list[Percentile]


class Percentiles(BaseModel):
    batting: PercentileGroup | None
    bowling: PercentileGroup | None


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
    percentiles: Percentiles
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
