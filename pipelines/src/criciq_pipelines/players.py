"""Player Lab tables for the serving database.

Every number on a player profile is a sum over these tables, so any split or
season window is one small aggregate at request time:

- ``player_batting_innings`` / ``player_bowling_innings``: one row per innings,
  with match context (season, venue, opposition, result, batting position).
- ``player_batting_cells`` / ``player_bowling_cells``: ball-level totals by
  season, phase and the opponent's type (bowler pace/spin, batter hand).
- ``league_phase_rates``: league-wide rates per season and phase.
- ``player_fielding``, ``player_seasons`` and ``player_index`` (the directory).

"Par" is what an average IPL batter (or bowler) would have produced from the
same balls: the league rate for that season and phase, summed over the
player's balls. It puts a 2010 strike rate and a 2025 one on the same footing,
and a death-overs specialist's economy against other death bowling.
Super overs are excluded throughout, as in official career records.
"""

from __future__ import annotations

import duckdb

from criciq_core.phases import default_phase_config

# Roles from balls per match over a career: a bowler averages at least
# BOWLER_BALLS legal balls a match; an all-rounder bowls at least
# ALL_ROUNDER_BOWL and also faces at least ALL_ROUNDER_BAT. Everyone else bats.
BOWLER_BALLS = 9
ALL_ROUNDER_BOWL = 6
ALL_ROUNDER_BAT = 7.5
# Stumpings only come from the wicketkeeper.
KEEPER_MIN_STUMPINGS = 2

PLAYER_TABLES = (
    "league_phase_rates",
    "player_batting_innings",
    "player_bowling_innings",
    "player_batting_cells",
    "player_bowling_cells",
    "player_fielding",
    "player_seasons",
    "player_index",
)


def _balls_sql() -> str:
    phase = default_phase_config().for_format("T20").sql_case("d.over_no")
    return f"""
    CREATE TEMP TABLE player_balls AS
    SELECT d.match_id, d.innings_no, d.seq_no, d.over_no, s.year AS season, {phase} AS phase,
           d.batter_id, d.non_striker_id, d.bowler_id,
           d.extras_wides = 0 AS faced,
           d.is_legal,
           d.runs_batter,
           d.runs_batter + d.extras_wides + d.extras_noballs AS conceded,
           d.is_four, d.is_six,
           d.extras_wides > 0 AS is_wide,
           d.extras_noballs > 0 AS is_noball,
           coalesce(pw.bowling_type, 'unknown') AS bowling_type,
           coalesce(pb.batting_hand, 'unknown') AS batting_hand
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    JOIN matches m USING (match_id)
    JOIN seasons s USING (season_id)
    LEFT JOIN players pw ON pw.player_id = d.bowler_id
    LEFT JOIN players pb ON pb.player_id = d.batter_id
    WHERE NOT i.is_super_over
    """


OUTS_SQL = """
CREATE TEMP TABLE player_outs AS
SELECT w.match_id, w.innings_no, w.seq_no, w.player_out_id AS player_id, w.kind,
       w.bowler_credited, b.bowler_id, b.season, b.phase, b.bowling_type, b.batting_hand
FROM wickets w
JOIN player_balls b USING (match_id, innings_no, seq_no)
WHERE w.is_dismissal
"""

LEAGUE_SQL = """
CREATE TABLE league_phase_rates AS
WITH balls AS (
    SELECT season, phase,
           count(*) FILTER (WHERE faced) AS bat_balls,
           sum(runs_batter) FILTER (WHERE faced) AS bat_runs,
           count(*) FILTER (WHERE faced AND (is_four OR is_six)) AS bat_boundaries,
           count(*) FILTER (WHERE faced AND runs_batter = 0) AS bat_dots,
           count(*) FILTER (WHERE is_legal) AS bowl_balls,
           sum(conceded) AS bowl_runs,
           count(*) FILTER (WHERE is_legal AND conceded = 0) AS bowl_dots,
           count(*) FILTER (WHERE is_four OR is_six) AS bowl_boundaries
    FROM player_balls GROUP BY ALL
),
outs AS (
    SELECT season, phase, count(*) AS bat_outs,
           count(*) FILTER (WHERE bowler_credited) AS bowl_wickets
    FROM player_outs GROUP BY ALL
)
SELECT b.season, b.phase, b.bat_balls, b.bowl_balls,
       b.bat_runs / b.bat_balls AS bat_runs_rate,
       coalesce(o.bat_outs, 0) / b.bat_balls AS bat_outs_rate,
       b.bat_boundaries / b.bat_balls AS bat_boundary_rate,
       b.bat_dots / b.bat_balls AS bat_dot_rate,
       b.bowl_runs / b.bowl_balls AS bowl_runs_rate,
       coalesce(o.bowl_wickets, 0) / b.bowl_balls AS bowl_wicket_rate,
       b.bowl_dots / b.bowl_balls AS bowl_dot_rate,
       b.bowl_boundaries / b.bowl_balls AS bowl_boundary_rate
FROM balls b LEFT JOIN outs o USING (season, phase)
ORDER BY season, phase
"""

# Par sums for the balls a batter faced / a bowler bowled (legal deliveries).
_BAT_PAR = """
    sum(r.bat_runs_rate) FILTER (WHERE b.faced) AS par_runs,
    sum(r.bat_outs_rate) FILTER (WHERE b.faced) AS par_outs,
    sum(r.bat_boundary_rate) FILTER (WHERE b.faced) AS par_boundaries,
    sum(r.bat_dot_rate) FILTER (WHERE b.faced) AS par_dots
"""
_BOWL_PAR = """
    sum(r.bowl_runs_rate) FILTER (WHERE b.is_legal) AS par_runs,
    sum(r.bowl_wicket_rate) FILTER (WHERE b.is_legal) AS par_wickets,
    sum(r.bowl_boundary_rate) FILTER (WHERE b.is_legal) AS par_boundaries,
    sum(r.bowl_dot_rate) FILTER (WHERE b.is_legal) AS par_dots
"""
_BAT_TOTALS = """
    count(*) FILTER (WHERE b.faced) AS balls,
    coalesce(sum(b.runs_batter), 0) AS runs,
    count(*) FILTER (WHERE b.is_four) AS fours,
    count(*) FILTER (WHERE b.is_six) AS sixes,
    count(*) FILTER (WHERE b.faced AND b.runs_batter = 0) AS dots,
"""
_BOWL_TOTALS = """
    count(*) FILTER (WHERE b.is_legal) AS balls,
    sum(b.conceded) AS runs,
    count(*) FILTER (WHERE b.is_legal AND b.conceded = 0) AS dots,
    count(*) FILTER (WHERE b.is_four) AS fours,
    count(*) FILTER (WHERE b.is_six) AS sixes,
    count(*) FILTER (WHERE b.is_wide) AS wides,
    count(*) FILTER (WHERE b.is_noball) AS noballs,
"""

# Match context shared by both innings tables; ``side`` is the player's team.
_CONTEXT = """
    s.year AS season, m.match_order, m.match_date, m.venue_id, m.is_playoff,
    {side}.franchise_id AS team_id, {other}.franchise_id AS opposition_id,
    CASE WHEN m.winner_id IS NULL THEN 'no_result'
         WHEN m.winner_id = {side}.team_season_id THEN 'won' ELSE 'lost' END AS result
"""

BATTING_INNINGS_SQL = f"""
CREATE TABLE player_batting_innings AS
WITH arrivals AS (
    -- Order of arrival: striker before non-striker on the first ball.
    SELECT match_id, innings_no, player_id, min(seq_no * 2 + priority) AS arrival
    FROM (SELECT match_id, innings_no, seq_no, batter_id AS player_id, 0 AS priority
          FROM player_balls
          UNION ALL
          SELECT match_id, innings_no, seq_no, non_striker_id, 1 FROM player_balls)
    GROUP BY ALL
),
positions AS (
    SELECT match_id, innings_no, player_id,
           row_number() OVER (PARTITION BY match_id, innings_no ORDER BY arrival) AS position
    FROM arrivals
),
faced AS (
    SELECT b.match_id, b.innings_no, b.batter_id AS player_id, {_BAT_TOTALS} {_BAT_PAR}
    FROM player_balls b JOIN league_phase_rates r USING (season, phase)
    GROUP BY ALL
),
outs AS (
    SELECT match_id, innings_no, player_id, arg_max(kind, seq_no) AS dismissal,
           arg_max(CASE WHEN bowler_credited THEN bowler_id END, seq_no) AS dismissed_by
    FROM player_outs GROUP BY ALL
)
SELECT p.player_id, p.match_id, p.innings_no,
       {_CONTEXT.format(side="bt", other="bw")},
       p.position::INTEGER AS position,
       coalesce(f.runs, 0)::INTEGER AS runs, coalesce(f.balls, 0)::INTEGER AS balls,
       coalesce(f.fours, 0)::INTEGER AS fours, coalesce(f.sixes, 0)::INTEGER AS sixes,
       coalesce(f.dots, 0)::INTEGER AS dots,
       o.player_id IS NOT NULL AS is_out, o.dismissal, o.dismissed_by,
       coalesce(f.par_runs, 0) AS par_runs, coalesce(f.par_outs, 0) AS par_outs,
       coalesce(f.par_boundaries, 0) AS par_boundaries, coalesce(f.par_dots, 0) AS par_dots
FROM positions p
JOIN innings i USING (match_id, innings_no)
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
JOIN team_seasons bt ON bt.team_season_id = i.batting_team_id
JOIN team_seasons bw ON bw.team_season_id = i.bowling_team_id
LEFT JOIN faced f USING (match_id, innings_no, player_id)
LEFT JOIN outs o USING (match_id, innings_no, player_id)
ORDER BY p.player_id, m.match_order, p.innings_no
"""

BOWLING_INNINGS_SQL = f"""
CREATE TABLE player_bowling_innings AS
WITH overs AS (
    SELECT match_id, innings_no, bowler_id, over_no,
           count(*) FILTER (WHERE is_legal) AS legal, sum(conceded) AS conceded
    FROM player_balls GROUP BY ALL
),
maidens AS (
    SELECT match_id, innings_no, bowler_id AS player_id,
           count(*) FILTER (WHERE legal >= 6 AND conceded = 0) AS maidens
    FROM overs GROUP BY ALL
),
bowled AS (
    SELECT b.match_id, b.innings_no, b.bowler_id AS player_id, {_BOWL_TOTALS} {_BOWL_PAR}
    FROM player_balls b JOIN league_phase_rates r USING (season, phase)
    GROUP BY ALL
),
wkts AS (
    SELECT match_id, innings_no, bowler_id AS player_id, count(*) AS wickets
    FROM player_outs WHERE bowler_credited GROUP BY ALL
)
SELECT b.player_id, b.match_id, b.innings_no,
       {_CONTEXT.format(side="bw", other="bt")},
       b.balls::INTEGER AS balls, b.runs::INTEGER AS runs,
       coalesce(w.wickets, 0)::INTEGER AS wickets, mo.maidens::INTEGER AS maidens,
       b.dots::INTEGER AS dots, b.fours::INTEGER AS fours, b.sixes::INTEGER AS sixes,
       b.wides::INTEGER AS wides, b.noballs::INTEGER AS noballs,
       coalesce(b.par_runs, 0) AS par_runs, coalesce(b.par_wickets, 0) AS par_wickets,
       coalesce(b.par_boundaries, 0) AS par_boundaries, coalesce(b.par_dots, 0) AS par_dots
FROM bowled b
JOIN maidens mo USING (match_id, innings_no, player_id)
JOIN innings i USING (match_id, innings_no)
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
JOIN team_seasons bt ON bt.team_season_id = i.batting_team_id
JOIN team_seasons bw ON bw.team_season_id = i.bowling_team_id
LEFT JOIN wkts w USING (match_id, innings_no, player_id)
ORDER BY b.player_id, m.match_order, b.innings_no
"""

BATTING_CELLS_SQL = f"""
CREATE TABLE player_batting_cells AS
WITH faced AS (
    SELECT b.batter_id AS player_id, b.season, b.phase, b.bowling_type, {_BAT_TOTALS} {_BAT_PAR}
    FROM player_balls b JOIN league_phase_rates r USING (season, phase)
    GROUP BY ALL
),
outs AS (
    -- A non-striker run out counts in the cell of the ball it happened on.
    SELECT player_id, season, phase, bowling_type, count(*) AS outs
    FROM player_outs GROUP BY ALL
)
SELECT player_id, season, phase, bowling_type,
       coalesce(f.balls, 0)::INTEGER AS balls, coalesce(f.runs, 0)::INTEGER AS runs,
       coalesce(f.fours, 0)::INTEGER AS fours, coalesce(f.sixes, 0)::INTEGER AS sixes,
       coalesce(f.dots, 0)::INTEGER AS dots, coalesce(o.outs, 0)::INTEGER AS outs,
       coalesce(f.par_runs, 0) AS par_runs, coalesce(f.par_outs, 0) AS par_outs,
       coalesce(f.par_boundaries, 0) AS par_boundaries, coalesce(f.par_dots, 0) AS par_dots
FROM faced f FULL OUTER JOIN outs o USING (player_id, season, phase, bowling_type)
ORDER BY player_id, season, phase, bowling_type
"""

BOWLING_CELLS_SQL = f"""
CREATE TABLE player_bowling_cells AS
WITH bowled AS (
    SELECT b.bowler_id AS player_id, b.season, b.phase, b.batting_hand, {_BOWL_TOTALS} {_BOWL_PAR}
    FROM player_balls b JOIN league_phase_rates r USING (season, phase)
    GROUP BY ALL
),
wkts AS (
    SELECT bowler_id AS player_id, season, phase, batting_hand, count(*) AS wickets
    FROM player_outs WHERE bowler_credited GROUP BY ALL
)
SELECT b.player_id, b.season, b.phase, b.batting_hand,
       b.balls::INTEGER AS balls, b.runs::INTEGER AS runs,
       coalesce(w.wickets, 0)::INTEGER AS wickets, b.dots::INTEGER AS dots,
       b.fours::INTEGER AS fours, b.sixes::INTEGER AS sixes,
       b.wides::INTEGER AS wides, b.noballs::INTEGER AS noballs,
       coalesce(b.par_runs, 0) AS par_runs, coalesce(b.par_wickets, 0) AS par_wickets,
       coalesce(b.par_boundaries, 0) AS par_boundaries, coalesce(b.par_dots, 0) AS par_dots
FROM bowled b LEFT JOIN wkts w USING (player_id, season, phase, batting_hand)
ORDER BY b.player_id, b.season, b.phase, b.batting_hand
"""

FIELDING_SQL = """
CREATE TABLE player_fielding AS
WITH listed AS (
    -- Catches and run outs by substitutes are not credited to the fielder,
    -- matching official records. Caught-and-bowled lists no fielder.
    SELECT match_id, innings_no, seq_no, kind,
           unnest(fielder_ids) AS player_id, unnest(fielder_is_substitute) AS sub
    FROM wickets WHERE is_dismissal AND kind IN ('caught', 'stumped', 'run out')
),
events AS (
    SELECT DISTINCT match_id, innings_no, seq_no, kind, player_id FROM listed WHERE NOT sub
    UNION ALL
    SELECT match_id, innings_no, seq_no, 'caught', bowler_id
    FROM wickets WHERE kind = 'caught and bowled'
)
SELECT e.player_id, e.match_id, s.year AS season,
       count(*) FILTER (WHERE e.kind = 'caught')::INTEGER AS catches,
       count(*) FILTER (WHERE e.kind = 'stumped')::INTEGER AS stumpings,
       count(*) FILTER (WHERE e.kind = 'run out')::INTEGER AS run_outs
FROM events e
JOIN innings i USING (match_id, innings_no)
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
WHERE NOT i.is_super_over
GROUP BY ALL
ORDER BY e.player_id, e.match_id
"""

SEASONS_SQL = """
CREATE TABLE player_seasons AS
SELECT mp.player_id, s.year AS season, t.franchise_id, count(*)::INTEGER AS matches
FROM match_players mp
JOIN matches m USING (match_id)
JOIN seasons s USING (season_id)
JOIN team_seasons t ON t.team_season_id = mp.team_season_id
GROUP BY ALL
ORDER BY mp.player_id, season
"""

INDEX_SQL = f"""
CREATE TABLE player_index AS
WITH apps AS (
    SELECT player_id, min(season) AS first_season, max(season) AS last_season,
           sum(matches)::INTEGER AS matches,
           arg_max(franchise_id, season * 1000 + matches) AS latest_team_id
    FROM player_seasons GROUP BY player_id
),
bat AS (
    SELECT player_id, sum(balls) AS balls FROM player_batting_innings GROUP BY player_id
),
bowl AS (
    SELECT player_id, sum(balls) AS balls FROM player_bowling_innings GROUP BY player_id
),
keep AS (
    SELECT player_id, sum(stumpings) AS stumpings FROM player_fielding GROUP BY player_id
),
rates AS (
    SELECT a.player_id, coalesce(bat.balls, 0) / a.matches AS bat_rate,
           coalesce(bowl.balls, 0) / a.matches AS bowl_rate,
           coalesce(keep.stumpings, 0) >= {KEEPER_MIN_STUMPINGS} AS is_keeper
    FROM apps a
    LEFT JOIN bat USING (player_id) LEFT JOIN bowl USING (player_id)
    LEFT JOIN keep USING (player_id)
)
SELECT p.player_id, p.name, p.full_name, p.country, p.date_of_birth, p.batting_hand,
       p.bowling_arm, p.bowling_type, p.bowling_style,
       CASE WHEN r.bowl_rate >= {ALL_ROUNDER_BOWL} AND r.bat_rate >= {ALL_ROUNDER_BAT}
                 THEN 'all_rounder'
            WHEN r.bowl_rate >= {BOWLER_BALLS} THEN 'bowler'
            ELSE 'batter' END AS role,
       r.is_keeper,
       a.first_season, a.last_season, a.matches, a.latest_team_id,
       lower(strip_accents(p.name || ' ' || coalesce(p.full_name, ''))) AS search_key
FROM players p
JOIN apps a USING (player_id)
JOIN rates r USING (player_id)
ORDER BY p.player_id
"""


def build_player_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the Player Lab tables from the serving copies of the core tables."""
    con.execute(_balls_sql())
    con.execute(OUTS_SQL)
    for sql in (
        LEAGUE_SQL,
        BATTING_INNINGS_SQL,
        BOWLING_INNINGS_SQL,
        BATTING_CELLS_SQL,
        BOWLING_CELLS_SQL,
        FIELDING_SQL,
        SEASONS_SQL,
        INDEX_SQL,
    ):
        con.execute(sql)
    con.execute("DROP TABLE player_outs")
    con.execute("DROP TABLE player_balls")
