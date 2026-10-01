"""SQL for the Player Lab (serving database tables built by criciq_pipelines.players)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from criciq_api.db import Database, Row

PlayerSort = Literal["matches", "runs", "wickets", "recent", "name"]
RoleFilter = Literal["batter", "bowler", "all_rounder", "keeper"]

_SORTS: dict[str, str] = {
    "matches": "a.matches DESC, i.name",
    "runs": "runs DESC, i.name",
    "wickets": "wickets DESC, i.name",
    "recent": "i.last_season DESC, a.matches DESC, i.name",
    "name": "i.name",
}

# Ball-level and innings-level totals share these sums so every split reports
# the same numbers the same way.
BATTING_SUMS = """
    sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs, sum(fours)::INTEGER AS fours,
    sum(sixes)::INTEGER AS sixes, sum(dots)::INTEGER AS dots,
    sum(par_runs) AS par_runs, sum(par_outs) AS par_outs,
    sum(par_boundaries) AS par_boundaries, sum(par_dots) AS par_dots
"""
BOWLING_SUMS = """
    sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs, sum(wickets)::INTEGER AS wickets,
    sum(dots)::INTEGER AS dots, sum(fours)::INTEGER AS fours, sum(sixes)::INTEGER AS sixes,
    sum(wides)::INTEGER AS wides, sum(noballs)::INTEGER AS noballs,
    sum(par_runs) AS par_runs, sum(par_wickets) AS par_wickets,
    sum(par_boundaries) AS par_boundaries, sum(par_dots) AS par_dots
"""


@dataclass(frozen=True)
class PlayerFilters:
    tokens: tuple[str, ...] = ()
    role: RoleFilter | None = None
    season: int | None = None
    team: str | None = None
    sort: PlayerSort = "matches"


def season_bounds(db: Database) -> tuple[int, int]:
    row = db.row("SELECT min(year) AS first, max(year) AS last FROM seasons")
    assert row is not None
    return int(row["first"]), int(row["last"])


def list_players(
    db: Database, filters: PlayerFilters, *, limit: int, offset: int
) -> tuple[list[Row], int]:
    scope: list[str] = []
    scope_params: list[object] = []
    if filters.season is not None:
        scope.append("season = ?")
        scope_params.append(filters.season)
    team_params = [*scope_params, filters.team] if filters.team else scope_params
    team_scope = [*scope, "team_id = ?"] if filters.team else scope
    team_where = f"WHERE {' AND '.join(team_scope)}" if team_scope else ""
    apps_scope = [*scope, "franchise_id = ?"] if filters.team else scope
    apps_where = f"WHERE {' AND '.join(apps_scope)}" if apps_scope else ""

    clauses: list[str] = []
    params: list[object] = []
    for token in filters.tokens:
        clauses.append("i.search_key LIKE ?")
        params.append(f"%{token}%")
    if filters.role == "keeper":
        clauses.append("i.is_keeper")
    elif filters.role is not None:
        clauses.append("i.role = ?")
        params.append(filters.role)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    base = f"""
        WITH apps AS (
            SELECT player_id, sum(matches)::INTEGER AS matches,
                   arg_max(franchise_id, season * 1000 + matches) AS team_id
            FROM player_seasons {apps_where} GROUP BY player_id
        ),
        bat AS (
            SELECT player_id, sum(runs)::INTEGER AS runs, sum(balls)::INTEGER AS balls,
                   count(*) FILTER (WHERE is_out)::INTEGER AS outs
            FROM player_batting_innings {team_where} GROUP BY player_id
        ),
        bowl AS (
            SELECT player_id, sum(wickets)::INTEGER AS wickets, sum(balls)::INTEGER AS balls,
                   sum(runs)::INTEGER AS runs
            FROM player_bowling_innings {team_where} GROUP BY player_id
        )
        SELECT i.player_id, i.name, i.full_name, i.country, i.role, i.is_keeper,
               i.first_season, i.last_season, a.matches,
               a.team_id, f.name AS team_name, f.primary_color AS team_color,
               coalesce(bat.runs, 0) AS runs, coalesce(bat.balls, 0) AS bat_balls,
               coalesce(bat.outs, 0) AS outs,
               coalesce(bowl.wickets, 0) AS wickets, coalesce(bowl.balls, 0) AS bowl_balls,
               coalesce(bowl.runs, 0) AS conceded
        FROM player_index i
        JOIN apps a USING (player_id)
        LEFT JOIN franchises f ON f.franchise_id = a.team_id
        LEFT JOIN bat USING (player_id)
        LEFT JOIN bowl USING (player_id)
        {where}
    """
    all_params = [*team_params, *team_params, *team_params, *params]
    total = int(db.scalar(f"SELECT count(*) FROM ({base})", all_params))
    rows = db.rows(
        f"{base} ORDER BY {_SORTS[filters.sort]} LIMIT ? OFFSET ?", [*all_params, limit, offset]
    )
    return rows, total


def get_player(db: Database, player_id: str) -> Row | None:
    return db.row("SELECT * FROM player_index WHERE player_id = ?", [player_id])


def get_teams(db: Database, player_id: str) -> list[Row]:
    return db.rows(
        """
        SELECT s.franchise_id, f.name, f.primary_color AS color,
               list(s.season ORDER BY s.season) AS seasons, sum(s.matches)::INTEGER AS matches
        FROM player_seasons s JOIN franchises f USING (franchise_id)
        WHERE s.player_id = ?
        GROUP BY ALL ORDER BY max(s.season) DESC, matches DESC
        """,
        [player_id],
    )


def _wpa_join(db: Database, role: str, alias: str) -> tuple[str, str]:
    """Expression and join for win probability added (NULL when the data was never scored)."""
    if not db.has_table("player_wpa"):
        return "NULL::DOUBLE", ""
    return (
        "w.wpa",
        f"LEFT JOIN player_wpa w ON w.player_id = {alias}.player_id "
        f"AND w.match_id = {alias}.match_id AND w.innings_no = {alias}.innings_no "
        f"AND w.role = '{role}'",
    )


def batting_summary(db: Database, player_id: str, first: int, last: int) -> Row | None:
    wpa, join = _wpa_join(db, "batting", "b")
    return db.row(
        f"""
        SELECT count(DISTINCT b.match_id)::INTEGER AS matches, count(*)::INTEGER AS innings,
               count(*) FILTER (WHERE b.is_out)::INTEGER AS outs,
               count(*) FILTER (WHERE b.runs >= 50 AND b.runs < 100)::INTEGER AS fifties,
               count(*) FILTER (WHERE b.runs >= 100)::INTEGER AS hundreds,
               count(*) FILTER (WHERE b.runs = 0 AND b.is_out)::INTEGER AS ducks,
               {BATTING_SUMS},
               sum({wpa}) AS wpa, count({wpa})::INTEGER AS wpa_innings
        FROM player_batting_innings b {join}
        WHERE b.player_id = ? AND b.season BETWEEN ? AND ?
        HAVING count(*) > 0
        """,
        [player_id, first, last],
    )


def highest_score(db: Database, player_id: str, first: int, last: int) -> Row | None:
    return db.row(
        """
        SELECT runs, NOT is_out AS not_out, match_id, season, opposition_id
        FROM player_batting_innings
        WHERE player_id = ? AND season BETWEEN ? AND ?
        ORDER BY runs DESC, is_out, match_order LIMIT 1
        """,
        [player_id, first, last],
    )


def bowling_summary(db: Database, player_id: str, first: int, last: int) -> Row | None:
    wpa, join = _wpa_join(db, "bowling", "b")
    return db.row(
        f"""
        SELECT count(DISTINCT b.match_id)::INTEGER AS matches, count(*)::INTEGER AS innings,
               count(*) FILTER (WHERE b.wickets = 4)::INTEGER AS four_wickets,
               count(*) FILTER (WHERE b.wickets >= 5)::INTEGER AS five_wickets,
               sum(b.maidens)::INTEGER AS maidens,
               {BOWLING_SUMS},
               sum({wpa}) AS wpa, count({wpa})::INTEGER AS wpa_innings
        FROM player_bowling_innings b {join}
        WHERE b.player_id = ? AND b.season BETWEEN ? AND ?
        HAVING count(*) > 0
        """,
        [player_id, first, last],
    )


def best_figures(db: Database, player_id: str, first: int, last: int) -> Row | None:
    return db.row(
        """
        SELECT wickets, runs, match_id, season, opposition_id
        FROM player_bowling_innings
        WHERE player_id = ? AND season BETWEEN ? AND ? AND balls > 0
        ORDER BY wickets DESC, runs, match_order LIMIT 1
        """,
        [player_id, first, last],
    )


def fielding(db: Database, player_id: str, first: int, last: int) -> Row:
    row = db.row(
        """
        SELECT coalesce(sum(catches), 0)::INTEGER AS catches,
               coalesce(sum(stumpings), 0)::INTEGER AS stumpings,
               coalesce(sum(run_outs), 0)::INTEGER AS run_outs
        FROM player_fielding WHERE player_id = ? AND season BETWEEN ? AND ?
        """,
        [player_id, first, last],
    )
    assert row is not None
    return row


def season_lines(db: Database, player_id: str, first: int, last: int) -> list[Row]:
    return db.rows(
        """
        WITH apps AS (
            SELECT season, list(franchise_id ORDER BY matches DESC) AS teams,
                   sum(matches)::INTEGER AS matches
            FROM player_seasons WHERE player_id = ? AND season BETWEEN ? AND ?
            GROUP BY season
        ),
        bat AS (
            SELECT season, count(*)::INTEGER AS innings, sum(runs)::INTEGER AS runs,
                   sum(balls)::INTEGER AS balls, count(*) FILTER (WHERE is_out)::INTEGER AS outs,
                   sum(par_runs) AS par_runs, max(runs)::INTEGER AS highest,
                   count(*) FILTER (WHERE runs >= 50 AND runs < 100)::INTEGER AS fifties,
                   count(*) FILTER (WHERE runs >= 100)::INTEGER AS hundreds
            FROM player_batting_innings WHERE player_id = ? GROUP BY season
        ),
        bowl AS (
            SELECT season, count(*)::INTEGER AS innings, sum(balls)::INTEGER AS balls,
                   sum(runs)::INTEGER AS runs, sum(wickets)::INTEGER AS wickets,
                   sum(par_runs) AS par_runs
            FROM player_bowling_innings WHERE player_id = ? GROUP BY season
        )
        SELECT a.season, a.teams, a.matches,
               bat.innings AS bat_innings, bat.runs AS bat_runs, bat.balls AS bat_balls,
               bat.outs AS bat_outs, bat.par_runs AS bat_par_runs, bat.highest, bat.fifties,
               bat.hundreds,
               bowl.innings AS bowl_innings, bowl.balls AS bowl_balls, bowl.runs AS bowl_runs,
               bowl.wickets, bowl.par_runs AS bowl_par_runs
        FROM apps a LEFT JOIN bat USING (season) LEFT JOIN bowl USING (season)
        ORDER BY a.season
        """,
        [player_id, first, last, player_id, player_id],
    )


def batting_cells(
    db: Database, player_id: str, first: int, last: int, by: Literal["phase", "bowling_type"]
) -> list[Row]:
    return db.rows(
        f"""
        SELECT {by} AS key, sum(outs)::INTEGER AS outs, {BATTING_SUMS}
        FROM player_batting_cells
        WHERE player_id = ? AND season BETWEEN ? AND ?
        GROUP BY {by}
        """,
        [player_id, first, last],
    )


def bowling_cells(
    db: Database, player_id: str, first: int, last: int, by: Literal["phase", "batting_hand"]
) -> list[Row]:
    return db.rows(
        f"""
        SELECT {by} AS key, {BOWLING_SUMS}
        FROM player_bowling_cells
        WHERE player_id = ? AND season BETWEEN ? AND ?
        GROUP BY {by}
        """,
        [player_id, first, last],
    )


# Innings-level split dimensions: SQL key expression per dimension.
BATTING_DIMENSIONS = {
    "season": "season::VARCHAR",
    "innings": "innings_no::VARCHAR",
    "position": """CASE WHEN position <= 2 THEN '1-2' WHEN position = 3 THEN '3'
                        WHEN position <= 5 THEN '4-5' WHEN position <= 7 THEN '6-7'
                        ELSE '8-11' END""",
    "opposition": "opposition_id",
    "venue": "venue_id",
    "result": "result",
    "stage": "CASE WHEN is_playoff THEN 'playoffs' ELSE 'league' END",
}
BOWLING_DIMENSIONS = {k: v for k, v in BATTING_DIMENSIONS.items() if k != "position"}


def batting_innings_split(
    db: Database, player_id: str, first: int, last: int, key_sql: str
) -> list[Row]:
    return db.rows(
        f"""
        SELECT {key_sql} AS key, count(*)::INTEGER AS innings,
               count(*) FILTER (WHERE is_out)::INTEGER AS outs,
               count(*) FILTER (WHERE runs >= 50)::INTEGER AS fifties,
               max(runs)::INTEGER AS highest, min(match_order) AS first_match,
               {BATTING_SUMS}
        FROM player_batting_innings
        WHERE player_id = ? AND season BETWEEN ? AND ?
        GROUP BY ALL
        """,
        [player_id, first, last],
    )


def bowling_innings_split(
    db: Database, player_id: str, first: int, last: int, key_sql: str
) -> list[Row]:
    return db.rows(
        f"""
        SELECT {key_sql} AS key, count(*)::INTEGER AS innings, min(match_order) AS first_match,
               {BOWLING_SUMS}
        FROM player_bowling_innings
        WHERE player_id = ? AND season BETWEEN ? AND ?
        GROUP BY ALL
        """,
        [player_id, first, last],
    )


def franchise_tags(db: Database) -> dict[str, Row]:
    return {
        r["franchise_id"]: r
        for r in db.rows("SELECT franchise_id, name, primary_color AS color FROM franchises")
    }


def venue_names(db: Database) -> dict[str, Row]:
    return {r["venue_id"]: r for r in db.rows("SELECT venue_id, name, city FROM venues")}


def recent_batting(db: Database, player_id: str, first: int, last: int, limit: int) -> list[Row]:
    wpa, join = _wpa_join(db, "batting", "b")
    return db.rows(
        f"""
        SELECT b.match_id, b.season, b.match_date, b.opposition_id, b.venue_id, b.position,
               b.runs, b.balls, b.fours, b.sixes, b.is_out, b.dismissal, b.result,
               {wpa} AS wpa
        FROM player_batting_innings b {join}
        WHERE b.player_id = ? AND b.season BETWEEN ? AND ?
        ORDER BY b.match_order DESC, b.innings_no DESC LIMIT ?
        """,
        [player_id, first, last, limit],
    )


def recent_bowling(db: Database, player_id: str, first: int, last: int, limit: int) -> list[Row]:
    wpa, join = _wpa_join(db, "bowling", "b")
    return db.rows(
        f"""
        SELECT b.match_id, b.season, b.match_date, b.opposition_id, b.venue_id,
               b.balls, b.runs, b.wickets, b.result, {wpa} AS wpa
        FROM player_bowling_innings b {join}
        WHERE b.player_id = ? AND b.season BETWEEN ? AND ?
        ORDER BY b.match_order DESC, b.innings_no DESC LIMIT ?
        """,
        [player_id, first, last, limit],
    )


def batting_dismissals(db: Database, player_id: str, first: int, last: int) -> list[Row]:
    return db.rows(
        """
        SELECT dismissal AS kind, count(*)::INTEGER AS count
        FROM player_batting_innings
        WHERE player_id = ? AND season BETWEEN ? AND ? AND is_out
        GROUP BY ALL ORDER BY count DESC, kind
        """,
        [player_id, first, last],
    )


def bowling_dismissals(db: Database, player_id: str, first: int, last: int) -> list[Row]:
    return db.rows(
        """
        SELECT w.kind, count(*)::INTEGER AS count
        FROM wickets w
        JOIN innings i USING (match_id, innings_no)
        JOIN matches m USING (match_id)
        JOIN seasons s USING (season_id)
        WHERE w.bowler_id = ? AND w.bowler_credited AND NOT i.is_super_over
          AND s.year BETWEEN ? AND ?
        GROUP BY ALL ORDER BY count DESC, kind
        """,
        [player_id, first, last],
    )


def batting_population(db: Database, first: int, last: int) -> list[Row]:
    """Per-player batting totals in the window, overall and by phase, for percentiles."""
    return db.rows(
        """
        SELECT player_id,
               sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs,
               sum(outs)::INTEGER AS outs, sum(fours + sixes)::INTEGER AS boundaries,
               sum(dots)::INTEGER AS dots, sum(par_runs) AS par_runs, sum(par_outs) AS par_outs,
               sum(par_boundaries) AS par_boundaries, sum(par_dots) AS par_dots,
               coalesce(sum(balls) FILTER (WHERE phase = 'powerplay'), 0)::INTEGER AS pp_balls,
               coalesce(sum(runs - par_runs) FILTER (WHERE phase = 'powerplay'), 0) AS pp_above,
               coalesce(sum(balls) FILTER (WHERE phase = 'death'), 0)::INTEGER AS death_balls,
               coalesce(sum(runs - par_runs) FILTER (WHERE phase = 'death'), 0) AS death_above
        FROM player_batting_cells WHERE season BETWEEN ? AND ?
        GROUP BY player_id
        """,
        [first, last],
    )


def bowling_population(db: Database, first: int, last: int) -> list[Row]:
    return db.rows(
        """
        SELECT player_id,
               sum(balls)::INTEGER AS balls, sum(runs)::INTEGER AS runs,
               sum(wickets)::INTEGER AS wickets, sum(fours + sixes)::INTEGER AS boundaries,
               sum(dots)::INTEGER AS dots, sum(par_runs) AS par_runs,
               sum(par_wickets) AS par_wickets, sum(par_boundaries) AS par_boundaries,
               sum(par_dots) AS par_dots,
               coalesce(sum(balls) FILTER (WHERE phase = 'powerplay'), 0)::INTEGER AS pp_balls,
               coalesce(sum(runs - par_runs) FILTER (WHERE phase = 'powerplay'), 0) AS pp_above,
               coalesce(sum(balls) FILTER (WHERE phase = 'death'), 0)::INTEGER AS death_balls,
               coalesce(sum(runs - par_runs) FILTER (WHERE phase = 'death'), 0) AS death_above
        FROM player_bowling_cells WHERE season BETWEEN ? AND ?
        GROUP BY player_id
        """,
        [first, last],
    )


def wpa_population(db: Database, role: str, first: int, last: int) -> dict[str, tuple[float, int]]:
    """Per-player (total WPA, innings) in the window."""
    if not db.has_table("player_wpa"):
        return {}
    rows = db.rows(
        """
        SELECT w.player_id, sum(w.wpa) AS wpa, count(*)::INTEGER AS innings
        FROM player_wpa w JOIN matches m USING (match_id) JOIN seasons s USING (season_id)
        WHERE w.role = ? AND s.year BETWEEN ? AND ?
        GROUP BY w.player_id
        """,
        [role, first, last],
    )
    return {r["player_id"]: (float(r["wpa"]), int(r["innings"])) for r in rows}
