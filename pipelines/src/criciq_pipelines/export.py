"""Export the read-only serving database the API ships with.

The serving database is a slim copy of the warehouse (only what the API reads)
plus precomputed, presentation-ready tables such as ``match_summaries``, so
request-time queries stay simple and fast. See docs/adr/0001.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

# Warehouse tables copied as-is.
COPIED_TABLES = (
    "meta",
    "competitions",
    "seasons",
    "franchises",
    "team_seasons",
    "venues",
    "matches",
    "innings",
    "deliveries",
    "wickets",
    "match_players",
    "substitutions",
)

_OVERS = "floor({b} / 6)::INTEGER::VARCHAR || '.' || ({b} % 6)::VARCHAR"

MATCH_SUMMARIES_SQL = f"""
CREATE TABLE match_summaries AS
WITH main_innings AS (
    SELECT match_id, innings_no, batting_team_id, runs, wickets, legal_balls, target_runs,
           target_balls
    FROM innings WHERE NOT is_super_over AND innings_no <= 2
),
sides AS (
    -- Side A batted first; with no innings at all, fall back to Cricsheet's team order.
    SELECT m.match_id,
           coalesce(i1.batting_team_id, m.team1_id) AS team_a_id,
           CASE WHEN coalesce(i1.batting_team_id, m.team1_id) = m.team1_id
                THEN m.team2_id ELSE m.team1_id END AS team_b_id
    FROM matches m
    LEFT JOIN main_innings i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
),
teams AS (
    SELECT t.team_season_id, t.display_name, f.franchise_id, f.primary_color
    FROM team_seasons t JOIN franchises f USING (franchise_id)
),
awards AS (
    SELECT x.match_id, list(coalesce(p.full_name, p.name, x.player_id)) AS names
    FROM (SELECT match_id, unnest(player_of_match_ids) AS player_id FROM matches) x
    LEFT JOIN players p USING (player_id)
    GROUP BY x.match_id
)
SELECT
    m.match_id,
    m.match_order,
    s.year AS season,
    m.match_date,
    m.match_number,
    m.stage,
    m.is_playoff,
    v.venue_id,
    v.name AS venue_name,
    v.city AS venue_city,
    sd.team_a_id,
    ta.display_name AS team_a_name,
    ta.franchise_id AS team_a_short,
    ta.primary_color AS team_a_color,
    sd.team_b_id,
    tb.display_name AS team_b_name,
    tb.franchise_id AS team_b_short,
    tb.primary_color AS team_b_color,
    ia.runs AS team_a_runs,
    ia.wickets AS team_a_wickets,
    CASE WHEN ia.legal_balls IS NOT NULL THEN {_OVERS.format(b="ia.legal_balls")} END
        AS team_a_overs,
    ib.runs AS team_b_runs,
    ib.wickets AS team_b_wickets,
    CASE WHEN ib.legal_balls IS NOT NULL THEN {_OVERS.format(b="ib.legal_balls")} END
        AS team_b_overs,
    ib.target_runs,
    m.toss_winner_id,
    tt.display_name AS toss_winner_name,
    m.toss_decision,
    m.outcome_type,
    m.winner_id,
    tw.display_name AS winner_name,
    m.win_by_runs,
    m.win_by_wickets,
    m.win_method,
    m.decided_by_super_over,
    CASE
        WHEN m.outcome_type = 'no_result' THEN 'No result'
        WHEN m.outcome_type = 'tie' THEN 'Match tied (' || tw.display_name || ' won the super over)'
        WHEN m.win_by_runs IS NOT NULL THEN
            tw.display_name || ' won by ' || m.win_by_runs
            || CASE WHEN m.win_by_runs = 1 THEN ' run' ELSE ' runs' END
            || CASE WHEN m.win_method IS NOT NULL THEN ' (' || m.win_method || ')' ELSE '' END
        WHEN m.win_by_wickets IS NOT NULL THEN
            tw.display_name || ' won by ' || m.win_by_wickets
            || CASE WHEN m.win_by_wickets = 1 THEN ' wicket' ELSE ' wickets' END
            || CASE WHEN m.win_method IS NOT NULL THEN ' (' || m.win_method || ')' ELSE '' END
        ELSE tw.display_name || ' won'
    END AS result_text,
    coalesce(aw.names, []::VARCHAR[]) AS player_of_match
FROM matches m
JOIN seasons s USING (season_id)
JOIN venues v USING (venue_id)
JOIN sides sd USING (match_id)
JOIN teams ta ON ta.team_season_id = sd.team_a_id
JOIN teams tb ON tb.team_season_id = sd.team_b_id
LEFT JOIN teams tt ON tt.team_season_id = m.toss_winner_id
LEFT JOIN teams tw ON tw.team_season_id = m.winner_id
LEFT JOIN main_innings ia ON ia.match_id = m.match_id AND ia.batting_team_id = sd.team_a_id
LEFT JOIN main_innings ib ON ib.match_id = m.match_id AND ib.batting_team_id = sd.team_b_id
LEFT JOIN awards aw ON aw.match_id = m.match_id
ORDER BY m.match_order
"""


def export_serving(warehouse: Path, target: Path) -> dict[str, int]:
    """Write the serving database to ``target`` atomically; return row counts."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)

    con = duckdb.connect(str(staging))
    try:
        con.execute(f"ATTACH '{warehouse.as_posix()}' AS wh (READ_ONLY)")
        for table in COPIED_TABLES:
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM wh.{table}")
        con.execute(
            """
            CREATE TABLE players AS
            SELECT player_id, name, full_name, country, batting_hand, bowling_arm,
                   bowling_type, bowling_style
            FROM wh.players
            """
        )
        con.execute(MATCH_SUMMARIES_SQL)
        con.execute("DETACH wh")
        counts = {
            table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]
            for table in (*COPIED_TABLES, "players", "match_summaries")
        }
        con.execute("CHECKPOINT")
    finally:
        con.close()
    os.replace(staging, target)
    return counts
