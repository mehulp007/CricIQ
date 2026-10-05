"""Tables the match simulator draws on, beyond the ball-outcome model.

The ball-outcome model covers what happens to the batter on a ball faced. A
whole match also needs:

- ``bowling_usage``: which overs each bowler bowled, per season and franchise,
  so a simulated captain hands the ball to bowlers the way their captains did.
- ``sim_league_rates``: per season, innings and phase, the number of legal
  balls, run outs (dismissals the ball model counts as runs) and the extras
  that came with each legal ball (wides and no-balls before it, byes and leg
  byes on it), counted by runs: 0, 1, 2, 3, 4 and 5 or more.

Super overs are excluded.
"""

from __future__ import annotations

import duckdb

from criciq_core.phases import default_phase_config

SIMULATION_TABLES = ("bowling_usage", "sim_league_rates")
EXTRAS_CAP = 5

BOWLING_USAGE_SQL = """
CREATE TABLE bowling_usage AS
WITH balls AS (
    SELECT d.match_id, d.innings_no, d.over_no, d.bowler_id, d.bowling_team_id,
           count(*) FILTER (WHERE d.is_legal) AS legal, min(d.seq_no) AS first_ball
    FROM deliveries d JOIN innings i USING (match_id, innings_no)
    WHERE NOT i.is_super_over
    GROUP BY d.match_id, d.innings_no, d.over_no, d.bowler_id, d.bowling_team_id
),
owner AS (
    -- An over belongs to the bowler who bowled most of its legal balls; on a
    -- split over (3 and 3), to the one who started it.
    SELECT match_id, innings_no, over_no,
           arg_max(bowler_id, legal * 1000000 - first_ball) AS player_id,
           arg_max(bowling_team_id, legal * 1000000 - first_ball) AS team_id
    FROM balls GROUP BY ALL
)
SELECT o.player_id, s.year AS season, t.franchise_id, o.over_no, count(*)::INTEGER AS overs,
       count(DISTINCT o.match_id)::INTEGER AS matches
FROM owner o
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
JOIN team_seasons t ON t.team_season_id = o.team_id
GROUP BY ALL
ORDER BY o.player_id, season, o.over_no
"""


def _rates_sql() -> str:
    phase = default_phase_config().for_format("T20").sql_case("d.over_no")
    extras = ", ".join(
        f"count(*) FILTER (WHERE x.extras = {k})::INTEGER AS x{k}" for k in range(EXTRAS_CAP)
    )
    return f"""
    CREATE TABLE sim_league_rates AS
    WITH slots AS (
        -- Illegal deliveries belong to the legal ball that follows them.
        SELECT d.match_id, d.innings_no,
               d.legal_ball_no + CASE WHEN d.is_legal THEN 0 ELSE 1 END AS slot,
               d.extras_wides + d.extras_noballs + d.extras_byes + d.extras_legbyes
                   + d.extras_penalty AS extras,
               d.is_legal, d.over_no
        FROM deliveries d JOIN innings i USING (match_id, innings_no)
        WHERE NOT i.is_super_over AND d.innings_no <= 2
    ),
    per_ball AS (
        SELECT match_id, innings_no, slot, least(sum(extras), {EXTRAS_CAP})::INTEGER AS extras,
               max(over_no) FILTER (WHERE is_legal) AS over_no
        FROM slots GROUP BY ALL
        HAVING bool_or(is_legal)
    ),
    run_outs AS (
        SELECT d.match_id, d.innings_no,
               d.legal_ball_no + CASE WHEN d.is_legal THEN 0 ELSE 1 END AS slot,
               count(*) AS run_outs
        FROM wickets w JOIN deliveries d USING (match_id, innings_no, seq_no)
        WHERE w.is_dismissal AND w.kind = 'run out'
        GROUP BY ALL
    )
    SELECT s.year AS season, x.innings_no, {phase.replace("d.over_no", "x.over_no")} AS phase,
           count(*)::INTEGER AS legal_balls,
           coalesce(sum(r.run_outs), 0)::INTEGER AS run_outs,
           {extras},
           count(*) FILTER (WHERE x.extras >= {EXTRAS_CAP})::INTEGER AS x{EXTRAS_CAP}
    FROM per_ball x
    JOIN matches m USING (match_id)
    JOIN seasons s USING (season_id)
    LEFT JOIN run_outs r USING (match_id, innings_no, slot)
    GROUP BY ALL
    ORDER BY season, x.innings_no, phase
    """


def build_simulation_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the simulator's usage and league-rate tables from the core tables."""
    con.execute(BOWLING_USAGE_SQL)
    con.execute(_rates_sql())
