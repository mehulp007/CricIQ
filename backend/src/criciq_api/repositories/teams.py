"""SQL for Team Analytics (serving tables built by criciq_pipelines.teams)."""

from __future__ import annotations

from criciq_api.db import Database, Row

# Results from one side's point of view; `played` counts no results too.
RECORD_SUMS = """
    count(*)::INTEGER AS played,
    count(*) FILTER (WHERE result = 'won')::INTEGER AS won,
    count(*) FILTER (WHERE result = 'lost')::INTEGER AS lost,
    count(*) FILTER (WHERE result = 'no_result')::INTEGER AS no_result
"""


def has_team_tables(db: Database) -> bool:
    return db.has_table("team_matches") and db.has_table("team_season_records")


def seasons(db: Database) -> list[int]:
    return [
        r["season"] for r in db.rows("SELECT DISTINCT season FROM team_season_records ORDER BY 1")
    ]


def franchises(db: Database) -> list[Row]:
    return db.rows(
        f"""
        WITH rec AS (
            SELECT franchise_id, {RECORD_SUMS} FROM team_matches GROUP BY franchise_id
        ),
        fin AS (
            SELECT franchise_id, count(*)::INTEGER AS seasons,
                   min(season) AS first_season, max(season) AS last_season,
                   coalesce(list(season ORDER BY season) FILTER (WHERE finish = 'champion'), [])
                       AS titles,
                   coalesce(list(season ORDER BY season)
                            FILTER (WHERE finish IN ('champion', 'runner_up')), []) AS finals,
                   coalesce(list(season ORDER BY season) FILTER (WHERE finish <> 'league'), [])
                       AS playoffs
            FROM team_season_records GROUP BY franchise_id
        ),
        names AS (
            SELECT franchise_id,
                   list(struct_pack(name := name, first_season := first, last_season := last)
                        ORDER BY first) AS names
            FROM (
                SELECT franchise_id, team_name AS name, min(season) AS first,
                       max(season) AS last
                FROM team_season_records GROUP BY ALL
            )
            GROUP BY franchise_id
        )
        SELECT f.franchise_id, f.name, f.primary_color AS color, f.secondary_color, f.is_active,
               fin.seasons, fin.first_season, fin.last_season, fin.titles, fin.finals,
               fin.playoffs, n.names, rec.played, rec.won, rec.lost, rec.no_result
        FROM franchises f
        JOIN rec USING (franchise_id)
        JOIN fin USING (franchise_id)
        JOIN names n USING (franchise_id)
        ORDER BY NOT f.is_active, f.name
        """
    )


def champions(db: Database) -> list[Row]:
    return db.rows(
        """
        SELECT c.season, c.franchise_id AS champion_id, r.franchise_id AS runner_up_id,
               f.match_id AS final_match_id, s.result_text
        FROM team_season_records c
        LEFT JOIN team_season_records r ON r.season = c.season AND r.finish = 'runner_up'
        LEFT JOIN team_matches f
            ON f.season = c.season AND f.stage = 'Final' AND f.franchise_id = c.franchise_id
        LEFT JOIN match_summaries s ON s.match_id = f.match_id
        WHERE c.finish = 'champion'
        ORDER BY c.season
        """
    )


def league_rates(db: Database) -> Row:
    row = db.row(
        """
        WITH decided AS (SELECT * FROM match_summaries WHERE outcome_type <> 'no_result')
        SELECT
            count(*)::INTEGER AS decided,
            count(*) FILTER (WHERE winner_id = team_b_id)::INTEGER AS chasing_won,
            count(*) FILTER (WHERE toss_winner_id IS NOT NULL)::INTEGER AS tosses,
            count(*) FILTER (WHERE winner_id = toss_winner_id)::INTEGER AS toss_won,
            (SELECT count(*) FROM team_matches WHERE venue_type = 'home' AND result <> 'no_result')
                ::INTEGER AS home_games,
            (SELECT count(*) FROM team_matches WHERE venue_type = 'home' AND result = 'won')
                ::INTEGER AS home_won,
            (SELECT count(*) FROM team_matches WHERE result = 'won' AND is_close)::INTEGER
                AS close
        FROM decided
        """
    )
    assert row is not None
    return row


def season_trends(db: Database) -> list[Row]:
    return db.rows(
        """
        WITH m AS (
            SELECT season,
                   count(*) FILTER (WHERE outcome_type <> 'no_result') AS decided,
                   count(*) FILTER (WHERE outcome_type <> 'no_result'
                                    AND winner_id = team_b_id) AS chasing_won,
                   count(*) FILTER (WHERE outcome_type <> 'no_result'
                                    AND toss_winner_id IS NOT NULL) AS tossed,
                   count(*) FILTER (WHERE outcome_type <> 'no_result'
                                    AND winner_id = toss_winner_id) AS toss_won,
                   count(*) FILTER (WHERE toss_decision IS NOT NULL) AS tosses,
                   count(*) FILTER (WHERE toss_decision = 'field') AS fielded,
                   avg(team_a_runs) FILTER (WHERE win_method IS NULL AND team_a_overs IS NOT NULL)
                       AS avg_first_innings
            FROM match_summaries GROUP BY season
        ),
        h AS (
            SELECT season, count(*) FILTER (WHERE result <> 'no_result') AS home_games,
                   count(*) FILTER (WHERE result = 'won') AS home_won
            FROM team_matches WHERE venue_type = 'home' GROUP BY season
        )
        SELECT m.*, coalesce(h.home_games, 0) AS home_games, coalesce(h.home_won, 0) AS home_won
        FROM m LEFT JOIN h USING (season)
        ORDER BY season
        """
    )


def standings(db: Database, season: int) -> list[Row]:
    return db.rows(
        """
        SELECT r.*, f.name, f.primary_color AS color
        FROM team_season_records r JOIN franchises f USING (franchise_id)
        WHERE r.season = ?
        ORDER BY r.position
        """,
        [season],
    )


def playoff_summaries(db: Database, season: int) -> list[Row]:
    return db.rows(
        "SELECT * FROM match_summaries WHERE season = ? AND is_playoff ORDER BY match_order",
        [season],
    )


# --------------------------------------------------------------------------- team profile


def team_seasons(db: Database, franchise_id: str) -> list[Row]:
    return db.rows(
        """
        SELECT r.*,
               coalesce(p.won, 0)::INTEGER AS playoff_won,
               coalesce(p.lost, 0)::INTEGER AS playoff_lost
        FROM team_season_records r
        LEFT JOIN (
            SELECT season, count(*) FILTER (WHERE result = 'won') AS won,
                   count(*) FILTER (WHERE result = 'lost') AS lost
            FROM team_matches WHERE franchise_id = ? AND is_playoff GROUP BY season
        ) p USING (season)
        WHERE r.franchise_id = ?
        ORDER BY r.season
        """,
        [franchise_id, franchise_id],
    )


_WINDOW = "franchise_id = ? AND season BETWEEN ? AND ?"


def _window(alias: str) -> str:
    return f"{alias}.franchise_id = ? AND {alias}.season BETWEEN ? AND ?"


def record(db: Database, franchise_id: str, first: int, last: int) -> Row:
    row = db.row(
        f"SELECT {RECORD_SUMS} FROM team_matches WHERE {_WINDOW}", [franchise_id, first, last]
    )
    assert row is not None
    return row


def record_splits(db: Database, franchise_id: str, first: int, last: int) -> list[Row]:
    """Records keyed by (group, key); keys with no matches are absent."""
    return db.rows(
        f"""
        SELECT 'innings' AS grp,
               CASE WHEN batted_first THEN 'bat_first' ELSE 'chasing' END AS key, {RECORD_SUMS}
        FROM team_matches WHERE {_WINDOW} AND batted_first IS NOT NULL GROUP BY ALL
        UNION ALL
        SELECT 'toss', CASE WHEN won_toss THEN 'won_toss' ELSE 'lost_toss' END, {RECORD_SUMS}
        FROM team_matches WHERE {_WINDOW} AND won_toss IS NOT NULL GROUP BY ALL
        UNION ALL
        SELECT 'venue', venue_type, {RECORD_SUMS}
        FROM team_matches WHERE {_WINDOW} GROUP BY ALL
        UNION ALL
        SELECT 'stage', CASE WHEN is_playoff THEN 'playoffs' ELSE 'league' END, {RECORD_SUMS}
        FROM team_matches WHERE {_WINDOW} GROUP BY ALL
        UNION ALL
        SELECT 'close', 'close', {RECORD_SUMS}
        FROM team_matches WHERE {_WINDOW} AND is_close GROUP BY ALL
        """,
        [franchise_id, first, last] * 5,
    )


def phases(db: Database, franchise_id: str, first: int, last: int) -> list[Row]:
    """Batting and bowling per phase with league par for the same seasons and phases."""
    return db.rows(
        """
        WITH league AS (
            SELECT season, phase, sum(runs) / sum(balls) AS runs_rate,
                   sum(wickets) / sum(balls) AS wicket_rate,
                   sum(fours + sixes) / sum(balls) AS boundary_rate,
                   sum(dots) / sum(balls) AS dot_rate
            FROM team_innings_phases WHERE season BETWEEN ? AND ? GROUP BY ALL
        ),
        sides AS (
            SELECT 'batting' AS role, * FROM team_innings_phases
            WHERE batting_id = ? AND season BETWEEN ? AND ?
            UNION ALL
            SELECT 'bowling', * FROM team_innings_phases
            WHERE bowling_id = ? AND season BETWEEN ? AND ?
        )
        SELECT s.role, s.phase,
               sum(s.balls)::INTEGER AS balls, sum(s.runs)::INTEGER AS runs,
               sum(s.wickets)::INTEGER AS wickets,
               sum(s.fours + s.sixes)::INTEGER AS boundaries, sum(s.dots)::INTEGER AS dots,
               sum(s.balls * l.runs_rate) AS par_runs,
               sum(s.balls * l.wicket_rate) AS par_wickets,
               sum(s.balls * l.boundary_rate) AS par_boundaries,
               sum(s.balls * l.dot_rate) AS par_dots
        FROM sides s JOIN league l USING (season, phase)
        GROUP BY ALL
        """,
        [first, last, franchise_id, first, last, franchise_id, first, last],
    )


def first_innings(db: Database, franchise_id: str, first: int, last: int) -> Row:
    row = db.row(
        f"""
        SELECT avg(runs_for) AS avg_runs, count(*)::INTEGER AS innings
        FROM team_matches
        WHERE {_WINDOW} AND batted_first AND win_method IS NULL AND runs_for IS NOT NULL
        """,
        [franchise_id, first, last],
    )
    assert row is not None
    return row


def extreme_total(
    db: Database, franchise_id: str, first: int, last: int, *, highest: bool
) -> Row | None:
    # The lowest total only counts completed innings: bowled out or batted out the 20 overs.
    completed = (
        "" if highest else "AND (wickets_for >= 10 OR balls_for >= 120) AND win_method IS NULL"
    )
    order = "runs_for DESC" if highest else "runs_for ASC"
    return db.row(
        f"""
        SELECT match_id, season, match_date, opponent_id, runs_for AS runs,
               wickets_for AS wickets, balls_for AS balls
        FROM team_matches
        WHERE {_WINDOW} AND runs_for IS NOT NULL {completed}
        ORDER BY {order}, match_order
        LIMIT 1
        """,
        [franchise_id, first, last],
    )


def biggest_win(db: Database, franchise_id: str, first: int, last: int, *, by: str) -> Row | None:
    order = (
        "t.win_by_runs DESC"
        if by == "runs"
        else "t.win_by_wickets DESC, t.balls_to_spare DESC NULLS LAST"
    )
    return db.row(
        f"""
        SELECT t.match_id, t.season, t.match_date, t.opponent_id, s.result_text
        FROM team_matches t JOIN match_summaries s USING (match_id)
        WHERE {_window("t")} AND t.result = 'won' AND t.win_by_{by} IS NOT NULL
        ORDER BY {order}, t.match_order
        LIMIT 1
        """,
        [franchise_id, first, last],
    )


def top_batters(
    db: Database,
    franchise_id: str,
    first: int,
    last: int,
    *,
    opponent: str | None = None,
    limit: int = 5,
) -> list[Row]:
    against = "AND b.opposition_id = ?" if opponent else ""
    params: list[object] = [franchise_id, first, last, *([opponent] if opponent else []), limit]
    return db.rows(
        f"""
        SELECT b.player_id, p.name, count(*)::INTEGER AS innings, sum(b.runs)::INTEGER AS runs,
               sum(b.balls)::INTEGER AS balls,
               count(*) FILTER (WHERE b.is_out)::INTEGER AS outs
        FROM player_batting_innings b JOIN players p USING (player_id)
        WHERE b.team_id = ? AND b.season BETWEEN ? AND ? {against}
        GROUP BY ALL
        ORDER BY runs DESC, balls, p.name
        LIMIT ?
        """,
        params,
    )


def top_bowlers(
    db: Database,
    franchise_id: str,
    first: int,
    last: int,
    *,
    opponent: str | None = None,
    limit: int = 5,
) -> list[Row]:
    against = "AND b.opposition_id = ?" if opponent else ""
    params: list[object] = [franchise_id, first, last, *([opponent] if opponent else []), limit]
    return db.rows(
        f"""
        SELECT b.player_id, p.name, count(*)::INTEGER AS innings,
               sum(b.wickets)::INTEGER AS wickets, sum(b.balls)::INTEGER AS balls,
               sum(b.runs)::INTEGER AS runs
        FROM player_bowling_innings b JOIN players p USING (player_id)
        WHERE b.team_id = ? AND b.season BETWEEN ? AND ? {against}
        GROUP BY ALL
        ORDER BY wickets DESC, runs, p.name
        LIMIT ?
        """,
        params,
    )


def opponents(db: Database, franchise_id: str, first: int, last: int) -> list[Row]:
    return db.rows(
        f"""
        SELECT opponent_id, {RECORD_SUMS} FROM team_matches WHERE {_WINDOW}
        GROUP BY opponent_id ORDER BY played DESC, opponent_id
        """,
        [franchise_id, first, last],
    )


def venues(db: Database, franchise_id: str, first: int, last: int, limit: int = 8) -> list[Row]:
    return db.rows(
        f"""
        SELECT t.venue_id, v.name, v.city, {RECORD_SUMS}
        FROM team_matches t JOIN venues v USING (venue_id)
        WHERE {_window("t")}
        GROUP BY ALL ORDER BY played DESC, v.name LIMIT ?
        """,
        [franchise_id, first, last, limit],
    )


def swings(
    db: Database, franchise_id: str, first: int, last: int, *, comebacks: bool, limit: int = 5
) -> list[Row]:
    """Wins from the side's lowest win probability, or defeats from its highest."""
    if not db.has_table("wp_predictions"):
        return []
    result = "won" if comebacks else "lost"
    pick = "arg_min" if comebacks else "arg_max"
    extreme = "min" if comebacks else "max"
    order = "ASC" if comebacks else "DESC"
    return db.rows(
        f"""
        WITH tm AS (
            SELECT match_id, match_order, season, match_date, opponent_id, batted_first
            FROM team_matches
            WHERE {_WINDOW} AND result = '{result}' AND batted_first IS NOT NULL
        ),
        wp AS (
            SELECT p.match_id, p.innings_no, p.seq_no,
                   CASE WHEN tm.batted_first THEN p.wp_team_a ELSE 1 - p.wp_team_a END AS wp
            FROM wp_predictions p JOIN tm USING (match_id)
            WHERE p.innings_no <= 2 AND p.wp_team_a IS NOT NULL
        ),
        peak AS (
            SELECT match_id, {extreme}(wp) AS wp,
                   {pick}(struct_pack(innings_no := innings_no, seq_no := seq_no), wp) AS at
            FROM wp GROUP BY match_id
        )
        SELECT tm.match_id, tm.season, tm.match_date, tm.opponent_id, s.result_text, k.wp,
               k.at.innings_no AS innings_no, k.at.seq_no AS seq_no,
               t.franchise_id AS batting_id, d.team_runs, d.team_wickets, d.legal_ball_no,
               i.target_runs, i.target_balls
        FROM peak k
        JOIN tm USING (match_id)
        JOIN match_summaries s USING (match_id)
        JOIN deliveries d
            ON d.match_id = k.match_id AND d.innings_no = k.at.innings_no
            AND d.seq_no = k.at.seq_no
        JOIN team_seasons t ON t.team_season_id = d.batting_team_id
        JOIN innings i ON i.match_id = d.match_id AND i.innings_no = d.innings_no
        ORDER BY k.wp {order}, tm.match_order DESC
        LIMIT ?
        """,
        [franchise_id, first, last, limit],
    )


# --------------------------------------------------------------------------- head to head


def meetings(db: Database, a: str, b: str, first: int, last: int) -> list[Row]:
    """Every meeting from A's side, oldest first, with B's form going into it."""
    return db.rows(
        """
        SELECT a.*, b.form_won AS opponent_form_won, b.form_decided AS opponent_form_decided
        FROM team_matches a
        JOIN team_matches b ON b.match_id = a.match_id AND b.franchise_id = a.opponent_id
        WHERE a.franchise_id = ? AND a.opponent_id = ? AND a.season BETWEEN ? AND ?
        ORDER BY a.match_order
        """,
        [a, b, first, last],
    )


def summaries(db: Database, match_ids: list[int]) -> list[Row]:
    if not match_ids:
        return []
    marks = ", ".join("?" for _ in match_ids)
    return db.rows(
        f"SELECT * FROM match_summaries WHERE match_id IN ({marks}) ORDER BY match_order DESC",
        match_ids,
    )
