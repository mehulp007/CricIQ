"""Tables behind the Records hub (extras: ``criciq_pipelines.extras``).

- ``partnerships``: every stand. A stand is the run of balls between two wickets with the
  same two batters, so a batter retiring hurt starts a new stand for the same wicket. It
  counts every run (extras too) and legal ball, each batter's runs off the bat, and whether
  it was unbroken (no wicket ended it).
- ``batting_milestones``: the balls each batter faced to reach 50 and 100 in an innings.
- ``match_swings``: each match's biggest change in win probability from one ball, as Model
  Insights finds it (the change from the previous ball of the same innings; matches whose
  result was decided by a revised target left out). Built once the database is scored.

Super overs are left out.
"""

from __future__ import annotations

import duckdb

RECORD_TABLES = ("partnerships", "batting_milestones")
MODEL_RECORD_TABLES = ("match_swings",)

PARTNERSHIPS_SQL = """
CREATE TABLE partnerships AS
WITH outs AS (
    SELECT match_id, innings_no, seq_no, count(*) AS dismissals
    FROM wickets WHERE is_dismissal GROUP BY ALL
),
balls AS (
    SELECT d.match_id, d.innings_no, d.seq_no, d.batter_id, d.non_striker_id,
           d.runs_total, d.runs_batter, d.is_legal, d.batting_team_id, d.bowling_team_id,
           coalesce(o.dismissals, 0) AS dismissals,
           -- Wickets fallen before this ball: the stand's wicket is one more.
           d.team_wickets - coalesce(o.dismissals, 0) + 1 AS wicket,
           least(d.batter_id, d.non_striker_id) AS first_id,
           greatest(d.batter_id, d.non_striker_id) AS second_id
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    LEFT JOIN outs o USING (match_id, innings_no, seq_no)
    WHERE NOT i.is_super_over
),
stands AS (
    SELECT match_id, innings_no, wicket, first_id, second_id,
           min(seq_no) AS first_seq, max(seq_no) AS last_seq,
           sum(runs_total)::INTEGER AS runs,
           count(*) FILTER (WHERE is_legal)::INTEGER AS balls,
           coalesce(sum(runs_batter) FILTER (WHERE batter_id = first_id), 0)::INTEGER
               AS first_runs,
           coalesce(sum(runs_batter) FILTER (WHERE batter_id = second_id), 0)::INTEGER
               AS second_runs,
           sum(dismissals) = 0 AS unbroken,
           any_value(batting_team_id) AS batting_team_id,
           any_value(bowling_team_id) AS bowling_team_id
    FROM balls
    GROUP BY match_id, innings_no, wicket, first_id, second_id
)
SELECT st.match_id, st.innings_no, st.wicket::INTEGER AS wicket, st.first_id, st.second_id,
       st.first_seq, st.last_seq, st.runs, st.balls, st.first_runs, st.second_runs,
       st.unbroken, s.year AS season, m.match_date, m.venue_id,
       tb.franchise_id AS team_id, tw.franchise_id AS opposition_id
FROM stands st
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
JOIN team_seasons tb ON tb.team_season_id = st.batting_team_id
JOIN team_seasons tw ON tw.team_season_id = st.bowling_team_id
ORDER BY st.match_id, st.innings_no, st.first_seq
"""

MILESTONES_SQL = """
CREATE TABLE batting_milestones AS
WITH faced AS (
    SELECT d.match_id, d.innings_no, d.batter_id AS player_id, d.seq_no,
           sum(d.runs_batter) OVER w AS runs,
           sum(CASE WHEN d.extras_wides = 0 THEN 1 ELSE 0 END) OVER w AS balls
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    WHERE NOT i.is_super_over
    WINDOW w AS (PARTITION BY d.match_id, d.innings_no, d.batter_id ORDER BY d.seq_no)
)
SELECT match_id, innings_no, player_id,
       min(balls) FILTER (WHERE runs >= 50)::INTEGER AS balls_to_50,
       min(balls) FILTER (WHERE runs >= 100)::INTEGER AS balls_to_100
FROM faced
GROUP BY ALL
HAVING max(runs) >= 50
ORDER BY match_id, innings_no, player_id
"""

SWINGS_SQL = """
CREATE TABLE match_swings AS
WITH w AS (
    SELECT match_id, innings_no, seq_no, wp_team_a,
           wp_team_a - lag(wp_team_a) OVER (
               PARTITION BY match_id, innings_no ORDER BY seq_no) AS delta
    FROM wp_predictions
),
ranked AS (
    SELECT w.*, row_number() OVER (
               PARTITION BY match_id ORDER BY abs(delta) DESC, innings_no, seq_no) AS rank
    FROM w WHERE seq_no > 0 AND delta IS NOT NULL
)
SELECT r.match_id, r.innings_no, r.seq_no, abs(r.delta) AS swing,
       -- The side whose chance rose, and its chance before and after the ball.
       CASE WHEN r.delta > 0 THEN ms.team_a_id ELSE ms.team_b_id END AS team_season_id,
       CASE WHEN r.delta > 0 THEN r.wp_team_a - r.delta ELSE 1 - (r.wp_team_a - r.delta) END
           AS wp_before,
       CASE WHEN r.delta > 0 THEN r.wp_team_a ELSE 1 - r.wp_team_a END AS wp_after,
       d.batter_id, d.bowler_id, s.year AS season, m.match_date, m.venue_id
FROM ranked r
JOIN deliveries d USING (match_id, innings_no, seq_no)
JOIN match_summaries ms USING (match_id)
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
WHERE r.rank = 1 AND ms.win_method IS NULL
ORDER BY r.match_id
"""


def build_record_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the Records hub's tables from a serving database's core tables."""
    con.execute(PARTNERSHIPS_SQL)
    con.execute(MILESTONES_SQL)


def build_model_record_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the records that read the model scores (``wp_predictions``)."""
    con.execute(SWINGS_SQL)
