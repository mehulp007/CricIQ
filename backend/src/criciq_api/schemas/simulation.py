"""Request and response models for the match simulator and the what-if sandbox."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from criciq_api.schemas.players import TeamTag

PlayerId = str


def _unique(ids: list[str]) -> list[str]:
    if len(set(ids)) != len(ids):
        raise ValueError("a player can only be picked once")
    return ids


# --------------------------------------------------------------------------- XIs


class SimPlayer(BaseModel):
    player_id: str
    name: str
    role: str | None
    batting_hand: str | None
    bowling_type: str | None
    position: float | None = Field(description="Usual batting position in recent seasons.")
    recent_overs: float = Field(description="Overs bowled in the player's last three seasons.")


class SquadPlayer(SimPlayer):
    matches: int = Field(description="Matches played for the side that season.")


class SimSquad(BaseModel):
    """A side's squad in one season: everyone who played for it, and its last XI."""

    team: TeamTag
    season: int
    display_name: str = Field(description="The side's name that season.")
    players: list[SquadPlayer] = Field(description="Most appearances first.")
    xi: list[str] = Field(description="The season's last playing XI, in batting order.")
    bowlers: list[str] = Field(description="That XI's default bowling options.")
    from_match: int | None
    match_date: dt.date | None


class SimSeasonTeam(BaseModel):
    team: TeamTag
    display_name: str


class SimSeason(BaseModel):
    season: int
    teams: list[SimSeasonTeam]


class SimXI(BaseModel):
    team: TeamTag | None
    from_match: int | None = Field(description="The match this XI is taken from, if any.")
    match_date: dt.date | None
    players: list[SimPlayer] = Field(description="In batting order.")
    bowlers: list[str] = Field(description="Default bowling options.")


class XIRequest(BaseModel):
    player_ids: list[PlayerId] = Field(min_length=2, max_length=11)

    _check = field_validator("player_ids")(_unique)


# --------------------------------------------------------------------------- simulation


class SideRequest(BaseModel):
    franchise_id: str | None = Field(default=None, max_length=8)
    batters: list[PlayerId] = Field(
        min_length=11, max_length=11, description="The XI in batting order."
    )
    bowlers: list[PlayerId] | None = Field(
        default=None,
        min_length=5,
        max_length=11,
        description="Bowling options from the XI (default: its regular bowlers).",
    )

    _check = field_validator("batters")(_unique)


class SimulationRequest(BaseModel):
    a: SideRequest
    b: SideRequest
    season: int | None = Field(
        default=None,
        ge=2008,
        le=2100,
        description=(
            "Play the match in this season: each side must come from its squad that season, "
            "and the scoring era, league rates and players' recent records are as of then. "
            "Empty means today's era with any players."
        ),
    )
    bat_first: Literal["a", "b"] | None = Field(
        default=None, description="Who bats first; empty means the toss decides (half each)."
    )
    simulations: int = Field(default=10_000, ge=500, le=10_000)
    seed: int | None = Field(default=None, ge=0, le=2**31)


class Distribution(BaseModel):
    mean: float
    p10: int
    p25: int
    p50: int
    p75: int
    p90: int
    bins: list[tuple[int, float]] = Field(
        description="Share of simulations in each 10-run bin, keyed by the bin's lower edge."
    )


class SimBatter(BaseModel):
    player_id: str
    name: str
    batted_pct: float = Field(description="Share of simulated innings in which they batted.")
    runs: int | None = Field(description="Typical (median) score in the innings they batted.")
    runs_low: int | None = Field(description="25th percentile of those scores.")
    runs_high: int | None = Field(description="75th percentile of those scores.")
    balls: int | None = Field(description="Typical (median) balls faced in those innings.")
    strike_rate: float | None
    fifty_pct: float = Field(description="Share of all simulated innings with 50 or more.")
    out_pct: float


class SimBowler(BaseModel):
    player_id: str
    name: str
    bowled_pct: float = Field(description="Share of simulated innings in which they bowled.")
    balls: int | None = Field(description="Typical (median) legal balls bowled when bowling.")
    runs: int | None = Field(description="Typical runs off the bat conceded when bowling.")
    wickets: int | None = Field(description="Typical wickets when bowling.")
    economy: float | None
    wicket_pct: float = Field(description="Share of all simulated innings with a wicket.")
    three_wicket_pct: float


class SideResult(BaseModel):
    key: Literal["a", "b"]
    team: TeamTag | None
    win_pct: float
    batting_first_pct: float
    first_innings: Distribution | None = Field(description="Total when batting first.")
    chase_pct: float | None = Field(description="Share of chases won when batting second.")
    batters: list[SimBatter]
    bowlers: list[SimBowler]


class SimulationResult(BaseModel):
    label: Literal["Model simulation"] = "Model simulation"
    simulations: int
    bat_first: Literal["a", "b"] | None
    a_win_pct: float
    b_win_pct: float
    tie_pct: float
    standard_error: float = Field(
        description="Monte Carlo standard error of the win shares (points)."
    )
    sides: list[SideResult]
    margin_runs: Distribution | None = Field(
        description="Winning margin when the side batting first wins."
    )
    seconds: float
    ball_model_version: str
    simulator_version: str
    conditions_sd: float


# --------------------------------------------------------------------------- what-if


class StateRequest(BaseModel):
    match_id: int
    innings_no: Literal[1, 2]
    seq_no: int = Field(ge=0, description="Replay position; 0 is before the first ball.")
    runs: int | None = Field(default=None, ge=0, le=400, description="Edited team total.")
    wickets: int | None = Field(default=None, ge=0, le=9, description="Edited wickets down.")
    simulations: int = Field(default=4000, ge=500, le=10_000)


class StateScore(BaseModel):
    runs: int
    wickets: int
    balls: int


class StateOutcome(BaseModel):
    score: StateScore
    simulated_win_pct: float = Field(description="Batting side's simulated chance of winning.")
    total: Distribution = Field(description="Simulated final total of the current innings.")


class StateResult(BaseModel):
    label: Literal["Model simulation"] = "Model simulation"
    batting: TeamTag
    bowling: TeamTag
    innings_no: int
    target: int | None
    model_win_pct: float | None = Field(
        description="Batting side's chance from the win probability model at the real state."
    )
    actual: StateOutcome
    edited: StateOutcome
    whatif_win_pct: float = Field(
        description=(
            "The model's chance moved by the simulated change on the log-odds scale; "
            "the simulated chance when the model has no value."
        )
    )
    simulations: int
    seconds: float
