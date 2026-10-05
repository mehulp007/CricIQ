"""Typed loaders for the version-controlled reference configuration in ``config/``.

These files are the curated "human knowledge" layer of the pipeline: which
raw team names belong to which franchise, which raw venue strings are the same
ground, and which scorecards are known to be correct.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from criciq_core.paths import config_dir


def _load_yaml(name: str, directory: Path | None) -> Any:
    path = (directory or config_dir()) / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------- competitions


class CricsheetSource(BaseModel):
    archive: str
    event_name: str


class CompetitionRules(BaseModel):
    impact_player_from: int | None = None


class Competition(BaseModel):
    id: str
    name: str
    short_name: str
    format: str
    gender: str
    team_type: str
    cricsheet: CricsheetSource
    rules: CompetitionRules = CompetitionRules()


class CompetitionsConfig(BaseModel):
    competitions: list[Competition]

    def get(self, competition_id: str) -> Competition:
        for competition in self.competitions:
            if competition.id == competition_id:
                return competition
        raise KeyError(f"unknown competition {competition_id!r}")


def load_competitions(directory: Path | None = None) -> CompetitionsConfig:
    return CompetitionsConfig.model_validate(_load_yaml("competitions.yaml", directory))


# --------------------------------------------------------------------------- franchises


class FranchiseName(BaseModel):
    name: str
    from_season: int = Field(alias="from")
    to_season: int | None = Field(default=None, alias="to")

    def covers(self, season: int) -> bool:
        return self.from_season <= season and (self.to_season is None or season <= self.to_season)


class FranchiseColors(BaseModel):
    primary: str
    secondary: str


class Franchise(BaseModel):
    id: str
    name: str
    colors: FranchiseColors
    names: list[FranchiseName]

    @property
    def first_season(self) -> int:
        return min(n.from_season for n in self.names)

    @property
    def last_season(self) -> int | None:
        ends = [n.to_season for n in self.names]
        return None if any(end is None for end in ends) else max(e for e in ends if e is not None)


class FranchisesConfig(BaseModel):
    competition: str
    franchises: list[Franchise]

    @model_validator(mode="after")
    def _unique(self) -> FranchisesConfig:
        ids = [f.id for f in self.franchises]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate franchise ids")
        return self

    def resolve(self, team_name: str, season: int) -> Franchise:
        """Franchise for a raw team name as used in a given season."""
        matches = [
            f for f in self.franchises for n in f.names if n.name == team_name and n.covers(season)
        ]
        if len(matches) != 1:
            raise LookupError(
                f"team name {team_name!r} in season {season} maps to "
                f"{len(matches)} franchises; update config/franchises.yaml"
            )
        return matches[0]


def load_franchises(directory: Path | None = None) -> FranchisesConfig:
    return FranchisesConfig.model_validate(_load_yaml("franchises.yaml", directory))


# --------------------------------------------------------------------------- venues


class Venue(BaseModel):
    id: str
    name: str
    city: str
    country: str
    notes: str | None = None
    aliases: list[str]


class VenuesConfig(BaseModel):
    venues: list[Venue]

    @model_validator(mode="after")
    def _unique(self) -> VenuesConfig:
        ids = [v.id for v in self.venues]
        aliases = [a for v in self.venues for a in v.aliases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate venue ids")
        if len(aliases) != len(set(aliases)):
            raise ValueError("a raw venue alias is listed under more than one venue")
        return self

    def alias_map(self) -> dict[str, str]:
        return {alias: v.id for v in self.venues for alias in v.aliases}


def load_venues(directory: Path | None = None) -> VenuesConfig:
    return VenuesConfig.model_validate(_load_yaml("venues.yaml", directory))


# --------------------------------------------------------------------------- golden matches


class GoldenInnings(BaseModel):
    team: str
    runs: int
    wickets: int
    target_runs: int | None = None
    target_overs: int | None = None


class GoldenResult(BaseModel):
    winner: str | None = None
    by_runs: int | None = None
    by_wickets: int | None = None
    method: str | None = None
    tie: bool = False
    super_over_winner: str | None = None


class GoldenMatch(BaseModel):
    match_id: int
    description: str
    date: dt.date
    innings: list[GoldenInnings] = []
    result: GoldenResult


class GoldenMatchesConfig(BaseModel):
    matches: list[GoldenMatch]


def load_golden_matches(directory: Path | None = None) -> GoldenMatchesConfig:
    return GoldenMatchesConfig.model_validate(_load_yaml("golden_matches.yaml", directory))


# --------------------------------------------------------------------------- league tables


class AbandonedFixture(BaseModel):
    season: int
    teams: tuple[str, str]


class VoidedMatch(BaseModel):
    match_id: int
    note: str


class TableRow(BaseModel):
    """One official league-table row: [franchise, won, lost, no result, points, NRR]."""

    franchise_id: str
    won: int
    lost: int
    no_result: int
    points: int
    nrr: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: Any) -> Any:
        if isinstance(value, list):
            keys = ("franchise_id", "won", "lost", "no_result", "points", "nrr")
            return dict(zip(keys, value, strict=True))
        return value


class LeagueTablesConfig(BaseModel):
    abandoned: list[AbandonedFixture] = []
    voided: list[VoidedMatch] = []
    seasons: dict[int, list[TableRow]] = Field(default_factory=dict)


def load_league_tables(directory: Path | None = None) -> LeagueTablesConfig:
    return LeagueTablesConfig.model_validate(_load_yaml("league_tables.yaml", directory))
