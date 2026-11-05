"""Tables behind the Phases page (an extra: ``criciq_pipelines.extras``).

- ``team_innings_overs``: runs, legal balls and wickets in every over of every innings
  (overs 1-indexed), for the over-by-over chart.
- ``phase_batting`` and ``phase_bowling``: each player's balls, runs, dismissals,
  boundaries and dots in each phase of each innings, with the match context the page
  filters on (season, the player's team and its opponent, the ground).

Phases follow each match's own format (``config/phases.yaml``); super overs are left
out. The batting and bowling definitions are the Player Lab's (``criciq_pipelines.players``):
a batter faces every ball but a wide; a bowler concedes the batter's runs, wides and
no-balls; a batter's dismissals include run outs, a bowler's wickets only those
credited to the bowler.
"""

from __future__ import annotations

import duckdb

from criciq_core.phases import default_phase_config

PHASE_TABLES = ("team_innings_overs", "phase_batting", "phase_bowling")


def _balls_sql() -> str:
    phase = default_phase_config().sql_case("d.over_no", "c.format")
    return f"""
    CREATE TEMP TABLE phase_balls AS
    SELECT d.match_id, d.innings_no, d.seq_no, d.over_no, s.year AS season, {phase} AS phase,
           m.venue_id, tb.franchise_id AS batting_id, tw.franchise_id AS bowling_id,
           d.batter_id, d.bowler_id, d.runs_total, d.runs_batter,
           d.extras_wides = 0 AS faced, d.is_legal,
           d.runs_batter + d.extras_wides + d.extras_noballs AS conceded,
           d.is_four, d.is_six
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    JOIN matches m USING (match_id)
    JOIN seasons s USING (season_id)
    JOIN competitions c ON c.competition_id = m.competition_id
    JOIN team_seasons tb ON tb.team_season_id = d.batting_team_id
    JOIN team_seasons tw ON tw.team_season_id = d.bowling_team_id
    WHERE NOT i.is_super_over
    """


OUTS_SQL = """
CREATE TEMP TABLE phase_outs AS
SELECT w.match_id, w.innings_no, w.seq_no, w.player_out_id, w.bowler_credited, b.bowler_id,
       b.phase
FROM wickets w JOIN phase_balls b USING (match_id, innings_no, seq_no)
WHERE w.is_dismissal
"""

OVERS_SQL = """
CREATE TABLE team_innings_overs AS
WITH fallen AS (
    SELECT DISTINCT match_id, innings_no, seq_no FROM phase_outs
)
SELECT b.match_id, b.innings_no, b.season, (b.over_no + 1)::INTEGER AS over, b.phase,
       b.batting_id, b.bowling_id, b.venue_id,
       sum(b.runs_total)::INTEGER AS runs,
       count(*) FILTER (WHERE b.is_legal)::INTEGER AS balls,
       count(f.seq_no)::INTEGER AS wickets
FROM phase_balls b LEFT JOIN fallen f USING (match_id, innings_no, seq_no)
GROUP BY ALL
ORDER BY b.match_id, b.innings_no, over
"""

BATTING_SQL = """
CREATE TABLE phase_batting AS
WITH faced AS (
    SELECT match_id, innings_no, phase, batter_id AS player_id, season, venue_id,
           batting_id AS team_id, bowling_id AS opposition_id,
           count(*) FILTER (WHERE faced)::INTEGER AS balls,
           coalesce(sum(runs_batter), 0)::INTEGER AS runs,
           count(*) FILTER (WHERE is_four)::INTEGER AS fours,
           count(*) FILTER (WHERE is_six)::INTEGER AS sixes,
           count(*) FILTER (WHERE faced AND runs_batter = 0)::INTEGER AS dots
    FROM phase_balls GROUP BY ALL
),
outs AS (
    SELECT match_id, innings_no, phase, player_out_id AS player_id, count(*)::INTEGER AS outs
    FROM phase_outs GROUP BY ALL
)
SELECT f.*, coalesce(o.outs, 0)::INTEGER AS outs
FROM faced f LEFT JOIN outs o USING (match_id, innings_no, phase, player_id)
ORDER BY f.match_id, f.innings_no, f.phase, f.player_id
"""

BOWLING_SQL = """
CREATE TABLE phase_bowling AS
WITH bowled AS (
    SELECT match_id, innings_no, phase, bowler_id AS player_id, season, venue_id,
           bowling_id AS team_id, batting_id AS opposition_id,
           count(*) FILTER (WHERE is_legal)::INTEGER AS balls,
           sum(conceded)::INTEGER AS runs,
           count(*) FILTER (WHERE is_legal AND conceded = 0)::INTEGER AS dots,
           count(*) FILTER (WHERE is_four)::INTEGER AS fours,
           count(*) FILTER (WHERE is_six)::INTEGER AS sixes
    FROM phase_balls GROUP BY ALL
),
wickets AS (
    SELECT match_id, innings_no, phase, bowler_id AS player_id, count(*)::INTEGER AS wickets
    FROM phase_outs WHERE bowler_credited GROUP BY ALL
)
SELECT b.*, coalesce(w.wickets, 0)::INTEGER AS wickets
FROM bowled b LEFT JOIN wickets w USING (match_id, innings_no, phase, player_id)
ORDER BY b.match_id, b.innings_no, b.phase, b.player_id
"""


def build_phase_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the Phases page's tables from a serving database's core tables."""
    con.execute(_balls_sql())
    con.execute(OUTS_SQL)
    for sql in (OVERS_SQL, BATTING_SQL, BOWLING_SQL):
        con.execute(sql)
    con.execute("DROP TABLE phase_outs")
    con.execute("DROP TABLE phase_balls")
