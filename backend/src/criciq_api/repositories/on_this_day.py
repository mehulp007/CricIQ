"""SQL for On This Day: the matches that started on a calendar date, with each one's best
innings, best bowling and (in a scored database) biggest win-probability swing."""

from __future__ import annotations

from criciq_api.db import Database, Row

_TEAM = """
    {side}.franchise_id AS {prefix}_id, f{prefix}.name AS {prefix}_name,
    f{prefix}.primary_color AS {prefix}_color
"""


def matches(db: Database, month: int, day: int) -> list[Row]:
    swings = db.has_table("match_swings")
    swing_columns = (
        """, w.innings_no AS swing_innings, w.seq_no AS swing_seq, w.swing,
        w.wp_before, w.wp_after, sw.franchise_id AS swing_team_id,
        fsw.name AS swing_team_name, fsw.primary_color AS swing_team_color"""
        if swings
        else ""
    )
    swing_join = (
        """LEFT JOIN match_swings w USING (match_id)
        LEFT JOIN team_seasons sw ON sw.team_season_id = w.team_season_id
        LEFT JOIN franchises fsw ON fsw.franchise_id = sw.franchise_id"""
        if swings
        else ""
    )
    return db.rows(
        f"""
        WITH day AS (
            SELECT * FROM match_summaries
            WHERE month(match_date) = ? AND day(match_date) = ?
        ),
        bat AS (
            SELECT b.match_id, b.player_id, b.runs, b.balls, b.is_out, b.team_id, b.opposition_id
            FROM player_batting_innings b JOIN day USING (match_id)
            QUALIFY row_number() OVER (
                PARTITION BY b.match_id ORDER BY b.runs DESC, b.balls, b.player_id) = 1
        ),
        bowl AS (
            SELECT w.match_id, w.player_id, w.wickets, w.runs, w.balls, w.team_id,
                   w.opposition_id
            FROM player_bowling_innings w JOIN day USING (match_id)
            WHERE w.balls > 0
            QUALIFY row_number() OVER (
                PARTITION BY w.match_id ORDER BY w.wickets DESC, w.runs, w.player_id) = 1
        )
        SELECT d.match_id, d.match_date, d.season, d.stage, d.is_playoff, d.venue_name,
               d.result_text, d.player_of_match,
               {_TEAM.format(side="ta", prefix="a")},
               {_TEAM.format(side="tb", prefix="b")},
               bat.player_id AS bat_id, coalesce(pbat.full_name, pbat.name) AS bat_name,
               bat.runs AS bat_runs, bat.balls AS bat_balls, bat.is_out AS bat_out,
               bat.team_id AS bat_team, bat.opposition_id AS bat_against,
               bowl.player_id AS bowl_id, coalesce(pbowl.full_name, pbowl.name) AS bowl_name,
               bowl.wickets AS bowl_wickets, bowl.runs AS bowl_runs, bowl.balls AS bowl_balls,
               bowl.team_id AS bowl_team, bowl.opposition_id AS bowl_against
               {swing_columns}
        FROM day d
        JOIN team_seasons ta ON ta.team_season_id = d.team_a_id
        JOIN team_seasons tb ON tb.team_season_id = d.team_b_id
        LEFT JOIN franchises fa ON fa.franchise_id = ta.franchise_id
        LEFT JOIN franchises fb ON fb.franchise_id = tb.franchise_id
        LEFT JOIN bat USING (match_id)
        LEFT JOIN players pbat ON pbat.player_id = bat.player_id
        LEFT JOIN bowl USING (match_id)
        LEFT JOIN players pbowl ON pbowl.player_id = bowl.player_id
        {swing_join}
        ORDER BY d.match_date DESC, d.match_id
        """,
        [month, day],
    )
