"""Typed loaders for the version-controlled reference configuration in ``config/``.

These files are the curated "human knowledge" layer of the pipeline: which
raw team names belong to which franchise, which raw venue strings are the same
ground, and which scorecards are known to be correct.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from criciq_core.paths import config_dir


def _load_yaml(name: str, directory: Path | None) -> Any:
    path = (directory or config_dir()) / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------- competitions


class MatchRule(BaseModel):
    """Which Cricsheet matches belong to a competition. Every given field must match."""

    event_name: str | None = None
    match_type: str | None = None
    team_type: str | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> MatchRule:
        if self.event_name is None and self.match_type is None:
            raise ValueError("a match rule needs an event_name or a match_type")
        return self


class CricsheetSource(BaseModel):
    archive: str
    match: MatchRule


class CompetitionRules(BaseModel):
    impact_player_from: int | None = None


class Competition(BaseModel):
    id: str
    name: str
    short_name: str
    format: Literal["T20", "ODI", "Test"]
    gender: Literal["male", "female"]
    team_type: Literal["club", "national"]
    teams: str
    strict: bool = False
    season_basis: Literal["label", "calendar"]
    switcher: bool = False
    cricsheet: CricsheetSource
    rules: CompetitionRules = CompetitionRules()

    def matches(self, info: dict[str, Any]) -> bool:
        """Whether a Cricsheet match (its ``info`` fields) belongs to this competition."""
        rule = self.cricsheet.match
        return (
            info.get("gender") == self.gender
            and (rule.event_name is None or info.get("event_name") == rule.event_name)
            and (rule.match_type is None or info.get("match_type") == rule.match_type)
            and (rule.team_type is None or info.get("team_type") == rule.team_type)
        )


class CompetitionsConfig(BaseModel):
    competitions: list[Competition]

    @model_validator(mode="after")
    def _unique(self) -> CompetitionsConfig:
        ids = [c.id for c in self.competitions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate competition ids")
        return self

    def get(self, competition_id: str) -> Competition:
        for competition in self.competitions:
            if competition.id == competition_id:
                return competition
        raise KeyError(f"unknown competition {competition_id!r}")

    def select(self, ids: list[str] | None) -> list[Competition]:
        """The listed competitions in config order (all of them when ``ids`` is None)."""
        if ids is None:
            return list(self.competitions)
        wanted = {i.upper() for i in ids}
        unknown = wanted - {c.id for c in self.competitions}
        if unknown:
            raise KeyError(f"unknown competitions: {sorted(unknown)}")
        return [c for c in self.competitions if c.id in wanted]

    def classify(self, info: dict[str, Any]) -> Competition | None:
        """The first competition a match belongs to, if any."""
        return next((c for c in self.competitions if c.matches(info)), None)


def load_competitions(directory: Path | None = None) -> CompetitionsConfig:
    return CompetitionsConfig.model_validate(_load_yaml("competitions.yaml", directory))


# --------------------------------------------------------------------------- teams


class TeamName(BaseModel):
    name: str
    from_season: int = Field(default=0, alias="from")
    to_season: int | None = Field(default=None, alias="to")

    @model_validator(mode="before")
    @classmethod
    def _from_string(cls, value: Any) -> Any:
        return {"name": value} if isinstance(value, str) else value

    def covers(self, season: int) -> bool:
        return self.from_season <= season and (self.to_season is None or season <= self.to_season)


class TeamColors(BaseModel):
    primary: str
    secondary: str


class Team(BaseModel):
    id: str
    name: str
    colors: TeamColors | None = None
    names: list[TeamName] = []

    @model_validator(mode="after")
    def _default_names(self) -> Team:
        if not self.names:
            self.names = [TeamName(name=self.name)]
        return self

    @property
    def first_season(self) -> int:
        return min(n.from_season for n in self.names)

    @property
    def last_season(self) -> int | None:
        ends = [n.to_season for n in self.names]
        return None if any(end is None for end in ends) else max(e for e in ends if e is not None)


class TeamsConfig(BaseModel):
    """Teams of one competition family (``config/teams/<name>.yaml``)."""

    name: str = ""
    teams: list[Team]

    @model_validator(mode="after")
    def _unique(self) -> TeamsConfig:
        ids = [t.id for t in self.teams]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate team ids in {self.name or 'teams'}")
        return self

    def resolve(self, team_name: str, season: int) -> Team:
        """Team for a raw team name as used in a given season."""
        matches = [
            t for t in self.teams for n in t.names if n.name == team_name and n.covers(season)
        ]
        if len(matches) != 1:
            raise LookupError(
                f"team name {team_name!r} in season {season} maps to "
                f"{len(matches)} teams; update config/teams/{self.name}.yaml"
            )
        return matches[0]


def load_teams(name: str, directory: Path | None = None) -> TeamsConfig:
    data = _load_yaml(f"teams/{name}.yaml", directory)
    return TeamsConfig.model_validate({**data, "name": name})


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


class VenuePlace(BaseModel):
    city: str
    country: str


class VenueCountriesConfig(BaseModel):
    """Countries (and merges) for grounds added automatically, outside venues.yaml."""

    cities: dict[str, str]
    venues: dict[str, VenuePlace] = {}
    merges: dict[str, str] = {}


def load_venue_countries(directory: Path | None = None) -> VenueCountriesConfig:
    return VenueCountriesConfig.model_validate(_load_yaml("venue_countries.yaml", directory))


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
    by_innings: int | None = None
    method: str | None = None
    tie: bool = False
    draw: bool = False
    super_over_winner: str | None = None


class GoldenMatch(BaseModel):
    match_id: int
    competition: str = "IPL"
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
