"""SQL for Phase Analysis (tables built by criciq_pipelines.phase_tables and .teams)."""

from __future__ import annotations

from typing import Any

from criciq_api.db import Database, Row
from criciq_api.repositories.common import FilterColumns, where
from criciq_api.schemas.common import Filters

PHASE_TABLES = ("team_innings_overs", "phase_batting", "phase_bowling", "team_innings_phases")

# A team's batting: its innings in the team tables (which have no opponent filter here).
_TEAM_BATTING = FilterColumns(
    season="t.season",
    team="t.batting_id",
    opponent=None,
    venue="t.venue_id",
    innings="t.innings_no",
)
_PLAYERS = FilterColumns(
    season="p.season", team="p.team_id", opponent=None, venue="p.venue_id", innings="p.innings_no"
)
# Matches: the team filter is applied by hand (either side), innings don't apply.
_MATCHES = FilterColumns(season="season", team=None, opponent=None, venue="venue_id", innings=None)


def has_phase_tables(db: Database) -> bool:
    return all(db.has_table(t) for t in PHASE_TABLES)


def phase_totals(db: Database, filters: Filters) -> list[Row]:
    clause, params = where(filters, _TEAM_BATTING)
    return db.rows(
        f"""
        SELECT t.phase, count(*)::INTEGER AS innings, sum(t.runs)::INTEGER AS runs,
               sum(t.balls)::INTEGER AS balls, sum(t.wickets)::INTEGER AS wickets,
               sum(t.fours)::INTEGER AS fours, sum(t.sixes)::INTEGER AS sixes,
               sum(t.dots)::INTEGER AS dots
        FROM (SELECT p.*, m.venue_id FROM team_innings_phases p JOIN matches m USING (match_id)) t
        WHERE {clause}
        GROUP BY t.phase
        """,
        params,
    )


def over_totals(db: Database, filters: Filters, block: int, max_over: int | None) -> list[Row]:
    clause, params = where(filters, _TEAM_BATTING)
    cap = "AND t.over <= ?" if max_over is not None else ""
    return db.rows(
        f"""
        SELECT ((t.over - 1) // ? * ? + 1)::INTEGER AS first_over,
               arg_min(t.phase, t.over) AS phase,
               count(DISTINCT t.match_id * 10 + t.innings_no)::INTEGER AS innings,
               sum(t.runs)::INTEGER AS runs, sum(t.balls)::INTEGER AS balls,
               sum(t.wickets)::INTEGER AS wickets
        FROM team_innings_overs t
        WHERE {clause} {cap}
        GROUP BY 1 ORDER BY 1
        """,
        [block, block, *params, *([max_over] if max_over is not None else [])],
    )


def _matches_cte(filters: Filters) -> tuple[str, list[Any]]:
    """Each match with its first innings: who batted first and second, and the result."""
    clause, params = where(filters.model_copy(update={"team": None, "innings": None}), _MATCHES)
    team = ""
    if filters.team is not None:
        team = "AND ? IN (first_id, second_id)"
        params.append(filters.team)
    return (
        f"""
        WITH base AS (
            SELECT m.match_id, s.year AS season, m.venue_id, m.outcome_type, m.toss_decision,
                   i.runs AS first_runs,
                   tf.franchise_id AS first_id, ts.franchise_id AS second_id,
                   tw.franchise_id AS winner_id, tt.franchise_id AS toss_id
            FROM matches m
            JOIN seasons s USING (season_id)
            JOIN innings i ON i.match_id = m.match_id AND i.innings_no = 1
            JOIN team_seasons tf ON tf.team_season_id = i.batting_team_id
            JOIN team_seasons ts ON ts.team_season_id = i.bowling_team_id
            LEFT JOIN team_seasons tw ON tw.team_season_id = m.winner_id
            LEFT JOIN team_seasons tt ON tt.team_season_id = m.toss_winner_id
        ),
        played AS (
            SELECT * FROM base
            WHERE {clause} {team} AND (winner_id IS NOT NULL OR outcome_type = 'draw')
        )
        """,
        params,
    )


def result_split(db: Database, filters: Filters) -> Row:
    cte, params = _matches_cte(filters)
    # Without a team every match counts on both sides; with one, the side it was on.
    first, second = ("TRUE", "TRUE") if filters.team is None else ("first_id = ?", "second_id = ?")
    team = [] if filters.team is None else [filters.team] * 8  # one per placeholder below
    found = db.row(
        f"""
        {cte}
        SELECT count(*)::INTEGER AS matches,
               count(*) FILTER (WHERE {first})::INTEGER AS first_matches,
               count(*) FILTER (WHERE {first} AND winner_id = first_id)::INTEGER AS first_won,
               count(*) FILTER (WHERE {first} AND outcome_type = 'draw')::INTEGER AS first_drawn,
               count(*) FILTER (WHERE {second})::INTEGER AS second_matches,
               count(*) FILTER (WHERE {second} AND winner_id = second_id)::INTEGER AS second_won,
               count(*) FILTER (WHERE {second} AND outcome_type = 'draw')::INTEGER AS second_drawn,
               avg(first_runs) FILTER (WHERE {first}) AS first_innings_average,
               avg(first_runs) FILTER (WHERE {first} AND winner_id = first_id) AS defended
        FROM played
        """,
        [*params, *team],
    )
    assert found is not None
    return found


def toss(db: Database, filters: Filters) -> list[Row]:
    cte, params = _matches_cte(filters)
    team = ""
    if filters.team is not None:
        team = "AND toss_id = ?"
        params.append(filters.team)
    return db.rows(
        f"""
        {cte}
        SELECT toss_decision AS decision, count(*)::INTEGER AS matches,
               count(*) FILTER (WHERE winner_id = toss_id)::INTEGER AS toss_winner_won
        FROM played
        WHERE toss_decision IS NOT NULL AND toss_id IS NOT NULL {team}
        GROUP BY 1 ORDER BY 1
        """,
        params,
    )


_NAMES = """
JOIN players pl USING (player_id)
LEFT JOIN franchises f ON f.franchise_id = q.team_id
"""


def batting_leaders(db: Database, filters: Filters, min_balls: int, limit: int) -> list[Row]:
    clause, params = where(filters, _PLAYERS)
    return db.rows(
        f"""
        WITH q AS (
            SELECT p.phase, p.player_id, mode(p.team_id) AS team_id,
                   count(*) FILTER (WHERE p.balls > 0 OR p.outs > 0)::INTEGER AS innings,
                   sum(p.balls)::INTEGER AS balls, sum(p.runs)::INTEGER AS runs,
                   sum(p.outs)::INTEGER AS outs, sum(p.fours + p.sixes)::INTEGER AS boundaries,
                   sum(p.dots)::INTEGER AS dots
            FROM phase_batting p
            WHERE {clause}
            GROUP BY p.phase, p.player_id
            HAVING sum(p.balls) >= ?
            QUALIFY row_number() OVER (
                PARTITION BY p.phase ORDER BY sum(p.runs) DESC, sum(p.balls), p.player_id
            ) <= ?
        )
        SELECT q.*, coalesce(pl.full_name, pl.name) AS name,
               f.name AS team_name, f.primary_color AS team_color
        FROM q {_NAMES}
        ORDER BY q.phase, q.runs DESC, q.balls, q.player_id
        """,
        [*params, min_balls, limit],
    )


def bowling_leaders(db: Database, filters: Filters, min_balls: int, limit: int) -> list[Row]:
    clause, params = where(filters, _PLAYERS)
    return db.rows(
        f"""
        WITH q AS (
            SELECT p.phase, p.player_id, mode(p.team_id) AS team_id,
                   count(*) FILTER (WHERE p.balls > 0)::INTEGER AS innings,
                   sum(p.balls)::INTEGER AS balls, sum(p.runs)::INTEGER AS runs,
                   sum(p.wickets)::INTEGER AS wickets, sum(p.dots)::INTEGER AS dots,
                   sum(p.fours + p.sixes)::INTEGER AS boundaries
            FROM phase_bowling p
            WHERE {clause}
            GROUP BY p.phase, p.player_id
            HAVING sum(p.balls) >= ?
            QUALIFY row_number() OVER (
                PARTITION BY p.phase
                ORDER BY sum(p.wickets) DESC, sum(p.runs) / sum(p.balls), p.player_id
            ) <= ?
        )
        SELECT q.*, coalesce(pl.full_name, pl.name) AS name,
               f.name AS team_name, f.primary_color AS team_color
        FROM q {_NAMES}
        ORDER BY q.phase, q.wickets DESC, q.runs / q.balls, q.player_id
        """,
        [*params, min_balls, limit],
    )


def grounds(db: Database, filters: Filters, limit: int) -> list[Row]:
    clause, params = where(filters, _TEAM_BATTING)
    return db.rows(
        f"""
        WITH t AS (
            SELECT p.*, m.venue_id FROM team_innings_phases p JOIN matches m USING (match_id)
        ),
        picked AS (
            SELECT t.venue_id, count(DISTINCT t.match_id)::INTEGER AS matches
            FROM t WHERE {clause}
            GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT ?
        )
        SELECT k.venue_id, v.name, v.city, k.matches, t.phase,
               sum(t.balls)::INTEGER AS balls, sum(t.runs)::INTEGER AS runs
        FROM picked k
        JOIN venues v USING (venue_id)
        JOIN t ON t.venue_id = k.venue_id
        WHERE {clause}
        GROUP BY ALL
        ORDER BY k.matches DESC, k.venue_id, t.phase
        """,
        [*params, limit, *params],
    )
