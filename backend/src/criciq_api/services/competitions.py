"""The players database's competitions (scopes) and players' careers across them.

Each scope is a schema of the players database (``criciq_pipelines.player_db``):
one per T20 competition, and ``t20`` for all of them together. ``scoped`` gives
the Player Lab services a database restricted to one scope.
"""

from __future__ import annotations

from typing import Any

from criciq_api.db import Database, Row, ScopedDatabase
from criciq_api.schemas.competitions import (
    CareerLine,
    CompetitionList,
    CompetitionScope,
    PlayerCareers,
    SeasonLabel,
)
from criciq_api.services.players import PlayerNotFoundError, _economy, _ratio, _strike_rate


class CompetitionNotFoundError(LookupError):
    pass


def scopes(db: Database) -> list[Row]:
    """Every scope, in display order (read once per dataset)."""
    if "scopes" not in db.cache:
        db.cache["scopes"] = db.rows("SELECT * FROM main.scopes ORDER BY display_order")
    found: list[Row] = db.cache["scopes"]
    return found


def _scope(db: Database, competition: str) -> Row:
    for scope in scopes(db):
        if scope["schema_name"] == competition.lower():
            return scope
    raise CompetitionNotFoundError(competition)


def scoped(db: Database, competition: str) -> ScopedDatabase:
    """The players database restricted to one scope, e.g. ``bbl`` or ``t20``."""
    scope = _scope(db, competition)
    return ScopedDatabase(db, scope["schema_name"], scope["format"])


def _labels(db: Database) -> dict[tuple[str, int], str]:
    """Season labels by (competition id, year)."""
    if "season_labels" not in db.cache:
        db.cache["season_labels"] = {
            (r["competition_id"], r["year"]): r["label"]
            for r in db.rows("SELECT competition_id, year, label FROM main.seasons")
        }
    found: dict[tuple[str, int], str] = db.cache["season_labels"]
    return found


def _label(db: Database, scope: Row, year: int) -> str:
    members = scope["competition_ids"]
    if len(members) == 1:
        return _labels(db).get((members[0], year), str(year))
    return str(year)


def list_competitions(db: Database) -> CompetitionList:
    counts = {
        r["competition_id"]: r
        for r in db.rows(
            """
            SELECT competition_id, count(*)::INTEGER AS matches
            FROM main.matches GROUP BY competition_id
            """
        )
    }
    players = {
        r["scope_id"]: r["players"]
        for r in db.rows(
            "SELECT scope_id, count(*)::INTEGER AS players FROM main.player_index GROUP BY ALL"
        )
    }
    years: dict[str, set[int]] = {}
    for competition_id, year in _labels(db):
        years.setdefault(competition_id, set()).add(year)
    items = []
    for scope in scopes(db):
        members: list[str] = scope["competition_ids"]
        played = sorted({y for m in members for y in years.get(m, set())})
        items.append(
            CompetitionScope(
                id=scope["schema_name"],
                name=scope["name"],
                short_name=scope["short_name"],
                format=scope["format"],
                competitions=members,
                matches=sum(counts[m]["matches"] for m in members if m in counts),
                players=players.get(scope["scope_id"], 0),
                seasons=[SeasonLabel(year=y, label=_label(db, scope, y)) for y in played],
            )
        )
    return CompetitionList(data_version=db.data_version, items=items)


def _sums(rows: list[Row], members: list[str], keys: tuple[str, ...]) -> dict[str, Any]:
    picked = [r for r in rows if r["competition_id"] in members]
    return {k: sum(r[k] or 0 for r in picked) for k in keys}


def get_careers(db: Database, player_id: str) -> PlayerCareers:
    bio = db.row(
        "SELECT player_id, name, full_name, country FROM main.players WHERE player_id = ?",
        [player_id],
    )
    if bio is None:
        raise PlayerNotFoundError(player_id)
    index = {
        r["scope_id"]: r
        for r in db.rows(
            """
            SELECT scope_id, matches, first_season, last_season
            FROM main.player_index WHERE player_id = ?
            """,
            [player_id],
        )
    }
    batting = db.rows(
        """
        SELECT competition_id, sum(runs)::INTEGER AS runs, sum(balls)::INTEGER AS balls,
               count(*) FILTER (WHERE is_out)::INTEGER AS outs, sum(par_runs) AS par_runs
        FROM main.player_batting_innings WHERE player_id = ? GROUP BY ALL
        """,
        [player_id],
    )
    bowling = db.rows(
        """
        SELECT competition_id, sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs,
               sum(wickets)::INTEGER AS wickets, sum(par_runs) AS par_runs
        FROM main.player_bowling_innings WHERE player_id = ? GROUP BY ALL
        """,
        [player_id],
    )
    careers = []
    for scope in scopes(db):
        found = index.get(scope["scope_id"])
        if found is None:
            continue
        members = scope["competition_ids"]
        bat = _sums(batting, members, ("runs", "balls", "outs", "par_runs"))
        bowl = _sums(bowling, members, ("balls", "runs", "wickets", "par_runs"))
        careers.append(
            CareerLine(
                competition=scope["schema_name"],
                name=scope["short_name"],
                matches=found["matches"],
                first_season=_label(db, scope, found["first_season"]),
                last_season=_label(db, scope, found["last_season"]),
                runs=bat["runs"],
                batting_average=_ratio(bat["runs"], bat["outs"]),
                strike_rate=_strike_rate(bat["runs"], bat["balls"]),
                par_strike_rate=_strike_rate(bat["par_runs"], bat["balls"]),
                wickets=bowl["wickets"],
                economy=_economy(bowl["runs"], bowl["balls"]),
                par_economy=_economy(bowl["par_runs"], bowl["balls"]),
            )
        )
    return PlayerCareers(
        player_id=bio["player_id"],
        name=bio["name"],
        full_name=bio["full_name"],
        country=bio["country"],
        careers=careers,
    )
