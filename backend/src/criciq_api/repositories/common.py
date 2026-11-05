"""SQL shared by the analysis pages: a competition's coverage and filter clauses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from criciq_api.db import Database, Row
from criciq_api.schemas.common import Filters


@dataclass(frozen=True)
class FilterColumns:
    """The column each filter applies to in one table (None: the table can't be filtered so)."""

    season: str | None = "season"
    team: str | None = "team_id"
    opponent: str | None = "opposition_id"
    venue: str | None = "venue_id"
    innings: str | None = "innings_no"


# The columns most player and team tables use.
DEFAULT_COLUMNS = FilterColumns()


def where(filters: Filters, columns: FilterColumns = DEFAULT_COLUMNS) -> tuple[str, list[Any]]:
    """A parameterised WHERE condition for ``filters`` (``TRUE`` when none is set).

    Values always travel as parameters, never in the SQL text. Setting a filter the
    table has no column for is a programming error.
    """
    clauses: list[str] = []
    params: list[Any] = []

    def add(column: str | None, name: str, op: str, value: Any) -> None:
        if value is None:
            return
        if column is None:
            raise ValueError(f"this table can't be filtered by {name}")
        clauses.append(f"{column} {op} ?")
        params.append(value)

    add(columns.season, "season", ">=", filters.season_from)
    add(columns.season, "season", "<=", filters.season_to)
    add(columns.team, "team", "=", filters.team)
    add(columns.opponent, "opponent", "=", filters.opponent)
    add(columns.venue, "venue", "=", filters.venue)
    add(columns.innings, "innings", "=", filters.innings)
    return (" AND ".join(clauses) or "TRUE", params)


def coverage(db: Database) -> Row:
    """The seasons, matches and dates the competition's data covers."""
    found = db.row(
        """
        SELECT min(s.year) AS first_season, max(s.year) AS last_season,
               arg_min(CASE WHEN ? THEN s.cricsheet_label ELSE s.year::VARCHAR END, s.year)
                   AS first_season_label,
               arg_max(CASE WHEN ? THEN s.cricsheet_label ELSE s.year::VARCHAR END, s.year)
                   AS last_season_label,
               count(m.match_id)::INTEGER AS matches,
               min(m.match_date) AS first_date, max(m.match_date) AS last_date
        FROM matches m JOIN seasons s USING (season_id)
        """,
        [db.season_spans_new_year, db.season_spans_new_year],
    )
    assert found is not None
    return found
