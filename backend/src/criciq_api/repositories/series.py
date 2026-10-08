"""Queries behind the series and tournament endpoints (``criciq_pipelines.events``)."""

from __future__ import annotations

from criciq_api.db import Database, Row


def has_events(db: Database) -> bool:
    return db.has_table("events")


def teams(db: Database) -> dict[str, Row]:
    """Every side's name and colour, by id (read once per dataset)."""
    if "event_teams" not in db.cache:
        db.cache["event_teams"] = {
            r["franchise_id"]: r
            for r in db.rows("SELECT franchise_id, name, primary_color AS color FROM franchises")
        }
    found: dict[str, Row] = db.cache["event_teams"]
    return found


def latest_date(db: Database) -> object:
    return db.scalar("SELECT max(end_date) FROM matches")


def list_events(
    db: Database,
    *,
    kind: str | None,
    year: int | None,
    team: str | None,
    major: bool | None,
    opponent: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Row], int]:
    where: list[str] = ["true"]
    params: list[object] = []
    if kind is not None:
        where.append("kind = ?")
        params.append(kind)
    if year is not None:
        where.append("? BETWEEN year(start_date) AND year(end_date)")
        params.append(year)
    if team is not None:
        where.append("list_contains(teams, ?)")
        params.append(team)
    if opponent is not None:
        where.append("list_contains(teams, ?)")
        params.append(opponent)
    if major is True:
        where.append("tournament_id IS NOT NULL")
    elif major is False:
        where.append("tournament_id IS NULL")
    clause = " AND ".join(where)
    total = int(db.scalar(f"SELECT count(*) FROM events WHERE {clause}", params) or 0)
    page = "" if limit is None else f"LIMIT {int(limit)} OFFSET {int(offset)}"
    rows = db.rows(
        f"SELECT * FROM events WHERE {clause} ORDER BY start_date DESC, event_id {page}", params
    )
    return rows, total


def years(db: Database) -> list[int]:
    return [
        int(r["y"])
        for r in db.rows(
            """
            SELECT DISTINCT unnest(range(year(start_date), year(end_date) + 1)) AS y FROM events
            ORDER BY y DESC
            """
        )
    ]


def get_event(db: Database, event_id: str) -> Row | None:
    return db.row("SELECT * FROM events WHERE event_id = ?", [event_id])


def event_of_match(db: Database, match_id: int) -> Row | None:
    if not has_events(db):
        return None
    return db.row(
        """
        SELECT e.event_id, e.name, e.season, e.kind, x.round
        FROM event_matches x JOIN events e USING (event_id) WHERE x.match_id = ?
        """,
        [match_id],
    )


def event_matches(db: Database, event_id: str) -> list[Row]:
    return db.rows(
        """
        SELECT s.*, x.round, x.round_order, x.knockout
        FROM event_matches x JOIN match_summaries s USING (match_id)
        WHERE x.event_id = ?
        ORDER BY s.match_order
        """,
        [event_id],
    )


def standings(db: Database, event_id: str) -> list[Row]:
    return db.rows(
        """
        SELECT * FROM event_standings WHERE event_id = ?
        ORDER BY round_order, round, position
        """,
        [event_id],
    )


def winner_lows(db: Database, event_id: str, *, draws: bool) -> dict[int, float]:
    """Each decided match's lowest chance of winning for its winner."""
    if not db.has_table("wp_predictions"):
        return {}
    other = "1 - p.wp_team_a - coalesce(p.wp_draw, 0)" if draws else "1 - p.wp_team_a"
    rows = db.rows(
        f"""
        SELECT s.match_id,
               min(CASE WHEN s.winner_id = s.team_a_id THEN p.wp_team_a ELSE {other} END) AS low
        FROM event_matches x
        JOIN match_summaries s USING (match_id)
        JOIN wp_predictions p USING (match_id)
        WHERE x.event_id = ? AND s.winner_id IS NOT NULL AND p.wp_team_a IS NOT NULL
        GROUP BY s.match_id
        """,
        [event_id],
    )
    return {int(r["match_id"]): float(r["low"]) for r in rows if r["low"] is not None}


def batters(db: Database, event_id: str, limit: int = 8) -> list[Row]:
    return db.rows(
        """
        SELECT b.player_id, p.name, b.team_id AS team, count(*)::INTEGER AS innings,
               sum(b.runs)::INTEGER AS runs, sum(b.balls)::INTEGER AS balls,
               count(*) FILTER (WHERE b.is_out)::INTEGER AS outs,
               max(b.runs)::INTEGER AS high,
               -- The highest score, not out if it was ever made not out.
               arg_max(NOT b.is_out, 2 * b.runs + (NOT b.is_out)::INTEGER) AS high_not_out,
               count(*) FILTER (WHERE b.runs >= 100)::INTEGER AS hundreds,
               count(*) FILTER (WHERE b.runs BETWEEN 50 AND 99)::INTEGER AS fifties
        FROM player_batting_innings b
        JOIN event_matches x USING (match_id)
        JOIN players p USING (player_id)
        WHERE x.event_id = ?
        GROUP BY ALL
        ORDER BY runs DESC, balls, p.name
        LIMIT ?
        """,
        [event_id, limit],
    )


def bowlers(db: Database, event_id: str, limit: int = 8) -> list[Row]:
    return db.rows(
        """
        SELECT b.player_id, p.name, b.team_id AS team, count(*)::INTEGER AS innings,
               sum(b.balls)::INTEGER AS balls, sum(b.runs)::INTEGER AS runs,
               sum(b.wickets)::INTEGER AS wickets,
               arg_max(b.wickets, b.wickets * 1000 - b.runs)::INTEGER AS best_wickets,
               arg_max(b.runs, b.wickets * 1000 - b.runs)::INTEGER AS best_runs
        FROM player_bowling_innings b
        JOIN event_matches x USING (match_id)
        JOIN players p USING (player_id)
        WHERE x.event_id = ?
        GROUP BY ALL
        HAVING sum(b.balls) > 0
        ORDER BY wickets DESC, runs, p.name
        LIMIT ?
        """,
        [event_id, limit],
    )


def decisive(db: Database, event_id: str, limit: int = 6) -> list[Row]:
    if not db.has_table("player_wpa"):
        return []
    return db.rows(
        """
        WITH sides AS (
            SELECT DISTINCT mp.match_id, mp.player_id, t.franchise_id
            FROM match_players mp
            JOIN team_seasons t USING (team_season_id)
            JOIN event_matches x USING (match_id)
            WHERE x.event_id = ?
        )
        SELECT w.player_id, p.name, s.franchise_id AS team,
               count(DISTINCT w.match_id)::INTEGER AS matches, sum(w.wpa) AS added
        FROM player_wpa w
        JOIN event_matches x USING (match_id)
        JOIN sides s ON s.match_id = w.match_id AND s.player_id = w.player_id
        JOIN players p ON p.player_id = w.player_id
        WHERE x.event_id = ?
        GROUP BY ALL
        ORDER BY added DESC, p.name
        LIMIT ?
        """,
        [event_id, event_id, limit],
    )
