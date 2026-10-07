"""Team Analytics tables for the serving database.

- ``team_matches``: one row per franchise per match, with the result, toss,
  totals, net run rate credit, home/away, whether the match was close and the
  side's form going into it (its previous ``FORM_MATCHES`` results).
- ``team_innings_phases``: runs, balls and wickets per innings and phase, the
  units of a team's batting and bowling profile.
- ``team_season_records``: the league table (points, net run rate and position,
  including abandoned fixtures Cricsheet has no record of; level teams are
  separated by wins, then net run rate) and each side's playoff finish.

Net run rate follows the playing conditions: a side bowled out is charged its
full quota of overs; when a chase is revised or ended by rain (D/L), the side
batting first is credited with the target minus one from the overs the chasing
side had; overs an umpire miscounted count as bowled. No results are left out.
The computed tables reproduce every official table (see config/league_tables.yaml).

In a league, a ground is a side's home in a season when the side played at least
``HOME_MIN_MATCHES`` league matches there and was in at least ``HOME_SHARE`` of
the league matches played there (in the IPL, only grounds in India count).
Seasons played at shared neutral venues (the IPL's 2009, 2020-2022 and UAE leg
of 2014, the PSL in the UAE, the CPL's single-island seasons) therefore have no
home sides, and adopted grounds such as Ranchi for CSK in 2014 count as home.
A national side is at home in its own country (``home_countries`` in
config/teams/national.yaml where that is more than one country, e.g. the West
Indies).
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from criciq_core.phases import default_phase_config
from criciq_pipelines.reference import LeagueTablesConfig

TEAM_TABLES = ("team_matches", "team_innings_phases", "team_season_records")

HOME_MIN_MATCHES = 2
HOME_SHARE = 0.75
# A close finish: a margin of at most this many runs, or a chase completed with at
# most this many balls to spare, or a tie (about one match in six).
CLOSE_RUNS = 5
CLOSE_BALLS = 2
# Matches of form before each match (about one season).
FORM_MATCHES = 14

TEAM_MATCHES_SQL = f"""
CREATE TEMP TABLE team_matches_base AS
WITH inn AS (
    SELECT i.match_id, i.innings_no, i.batting_team_id, i.bowling_team_id, i.runs, i.wickets,
           i.legal_balls, i.target_runs, i.target_balls,
           coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls,
           coalesce(list_sum([6 - (x->>'balls')::INTEGER
                              FOR x IN json_extract(i.miscounted_overs, '$.*')]), 0)::INTEGER
               AS miscounted,
           (i.wickets >= 10 OR (i.wickets = 9 AND len(coalesce(i.absent_hurt_ids, [])) > 0))
               AS all_out
    FROM innings i JOIN matches m USING (match_id)
    WHERE NOT i.is_super_over AND i.innings_no <= 2
),
credit AS (
    SELECT a.match_id, a.batting_team_id,
           CASE WHEN a.innings_no = 1 AND m.win_method IS NOT NULL AND b.target_runs IS NOT NULL
                THEN b.target_runs - 1 ELSE a.runs END AS runs,
           CASE WHEN a.innings_no = 1 AND m.win_method IS NOT NULL AND b.target_balls IS NOT NULL
                THEN b.target_balls
                WHEN a.all_out THEN a.max_balls
                ELSE a.legal_balls + a.miscounted END AS balls
    FROM inn a JOIN matches m USING (match_id)
    LEFT JOIN inn b ON b.match_id = a.match_id AND b.innings_no = 2
),
league_venue AS (
    SELECT s.year AS season, m.venue_id, t.franchise_id, count(*) AS n
    FROM matches m JOIN seasons s USING (season_id)
    JOIN venues v USING (venue_id)
    JOIN team_seasons t ON t.team_season_id IN (m.team1_id, m.team2_id)
    WHERE m.stage = 'League'
      AND (getvariable('home_country') IS NULL OR v.country = getvariable('home_country'))
    GROUP BY s.year, m.venue_id, t.franchise_id
),
national_home AS (
    SELECT DISTINCT s.year AS season, m.venue_id, t.franchise_id
    FROM matches m JOIN seasons s USING (season_id)
    JOIN venues v USING (venue_id)
    JOIN team_seasons t ON t.team_season_id IN (m.team1_id, m.team2_id)
    JOIN home_countries h ON h.franchise_id = t.franchise_id AND h.country = v.country
),
home AS (
    SELECT season, venue_id, franchise_id
    FROM (
        SELECT *, sum(n) OVER (PARTITION BY season, venue_id) / 2 AS venue_matches
        FROM league_venue
    )
    WHERE n >= {HOME_MIN_MATCHES} AND n >= {HOME_SHARE} * venue_matches
      AND NOT getvariable('national')
    UNION ALL
    SELECT season, venue_id, franchise_id FROM national_home
),
sides AS (
    SELECT m.*, s.year AS season,
           t.team_season_id AS team_id, t.franchise_id, t.display_name AS team_name,
           o.team_season_id AS opponent_team_id, o.franchise_id AS opponent_id,
           o.display_name AS opponent_name
    FROM matches m JOIN seasons s USING (season_id)
    JOIN team_seasons t ON t.team_season_id IN (m.team1_id, m.team2_id)
    JOIN team_seasons o ON o.team_season_id IN (m.team1_id, m.team2_id)
        AND o.team_season_id <> t.team_season_id
)
SELECT x.match_id, x.match_order, x.season, x.match_date, x.stage, x.is_playoff, x.venue_id,
       x.franchise_id, x.team_id, x.team_name, x.opponent_id, x.opponent_team_id,
       x.opponent_name,
       CASE WHEN x.outcome_type = 'no_result' THEN 'no_result'
            WHEN x.winner_id = x.team_id THEN 'won' ELSE 'lost' END AS result,
       x.outcome_type = 'tie' AS tied,
       x.stage = 'League' AND v.match_id IS NULL AS in_table,
       CASE WHEN bat.innings_no IS NOT NULL THEN bat.innings_no = 1
            WHEN bowl.innings_no IS NOT NULL THEN bowl.innings_no = 2 END AS batted_first,
       x.toss_winner_id = x.team_id AS won_toss,
       x.toss_decision,
       bat.runs AS runs_for, bat.wickets AS wickets_for, bat.legal_balls AS balls_for,
       bowl.runs AS runs_against, bowl.wickets AS wickets_against,
       bowl.legal_balls AS balls_against,
       CASE WHEN x.outcome_type <> 'no_result' THEN cf.runs END AS nrr_runs_for,
       CASE WHEN x.outcome_type <> 'no_result' THEN cf.balls END AS nrr_balls_for,
       CASE WHEN x.outcome_type <> 'no_result' THEN ca.runs END AS nrr_runs_against,
       CASE WHEN x.outcome_type <> 'no_result' THEN ca.balls END AS nrr_balls_against,
       x.win_by_runs, x.win_by_wickets, x.win_method,
       CASE WHEN x.outcome_type = 'win' AND x.win_by_wickets IS NOT NULL
            THEN chase.max_balls - chase.legal_balls END AS balls_to_spare,
       coalesce(
           x.outcome_type = 'tie'
           OR x.win_by_runs <= {CLOSE_RUNS}
           OR (x.win_by_wickets IS NOT NULL
               AND chase.max_balls - chase.legal_balls <= {CLOSE_BALLS}),
           false
       ) AS is_close,
       CASE WHEN h.franchise_id IS NOT NULL THEN 'home'
            WHEN ho.franchise_id IS NOT NULL THEN 'away'
            ELSE 'neutral' END AS venue_type
FROM sides x
LEFT JOIN inn bat ON bat.match_id = x.match_id AND bat.batting_team_id = x.team_id
LEFT JOIN inn bowl ON bowl.match_id = x.match_id AND bowl.bowling_team_id = x.team_id
LEFT JOIN inn chase ON chase.match_id = x.match_id AND chase.innings_no = 2
LEFT JOIN credit cf ON cf.match_id = x.match_id AND cf.batting_team_id = x.team_id
LEFT JOIN credit ca ON ca.match_id = x.match_id AND ca.batting_team_id = x.opponent_team_id
LEFT JOIN voided_matches v ON v.match_id = x.match_id
LEFT JOIN home h
    ON h.season = x.season AND h.venue_id = x.venue_id AND h.franchise_id = x.franchise_id
LEFT JOIN home ho
    ON ho.season = x.season AND ho.venue_id = x.venue_id AND ho.franchise_id = x.opponent_id
"""

# Form before each match: the side's results in its previous FORM_MATCHES matches
# (no results do not count), so form never includes the match it describes.
FORM_SQL = f"""
CREATE TABLE team_matches AS
SELECT *,
       coalesce(sum((result = 'won')::INTEGER) OVER prior, 0)::INTEGER AS form_won,
       coalesce(count(*) FILTER (WHERE result <> 'no_result') OVER prior, 0)::INTEGER
           AS form_decided
FROM team_matches_base
WINDOW prior AS (
    PARTITION BY franchise_id ORDER BY match_order
    ROWS BETWEEN {FORM_MATCHES} PRECEDING AND 1 PRECEDING
)
ORDER BY match_order, franchise_id
"""


def _phases_sql() -> str:
    phase = default_phase_config().sql_case("d.over_no", "c.format")
    return f"""
    CREATE TABLE team_innings_phases AS
    SELECT d.match_id, d.innings_no, s.year AS season, {phase} AS phase,
           tb.franchise_id AS batting_id, tw.franchise_id AS bowling_id,
           sum(d.runs_total)::INTEGER AS runs,
           count(*) FILTER (WHERE d.is_legal)::INTEGER AS balls,
           count(w.match_id)::INTEGER AS wickets,
           count(*) FILTER (WHERE d.is_four)::INTEGER AS fours,
           count(*) FILTER (WHERE d.is_six)::INTEGER AS sixes,
           count(*) FILTER (WHERE d.is_legal AND d.runs_total = 0)::INTEGER AS dots
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    JOIN matches m USING (match_id)
    JOIN seasons s USING (season_id)
    JOIN competitions c ON c.competition_id = m.competition_id
    JOIN team_seasons tb ON tb.team_season_id = d.batting_team_id
    JOIN team_seasons tw ON tw.team_season_id = d.bowling_team_id
    LEFT JOIN (
        SELECT DISTINCT match_id, innings_no, seq_no FROM wickets WHERE is_dismissal
    ) w USING (match_id, innings_no, seq_no)
    WHERE NOT i.is_super_over
    GROUP BY ALL
    ORDER BY d.match_id, d.innings_no, phase
    """


RECORDS_SQL = """
    CREATE TABLE team_season_records AS
    WITH entrants AS (
        SELECT s.year AS season, t.franchise_id, t.team_season_id AS team_id,
               t.display_name AS team_name
        FROM team_seasons t JOIN seasons s USING (season_id)
        WHERE EXISTS (
            SELECT 1 FROM team_matches x WHERE x.team_id = t.team_season_id
        )
    ),
    played AS (
        SELECT season, franchise_id,
               count(*) FILTER (WHERE result = 'won')::INTEGER AS won,
               count(*) FILTER (WHERE result = 'lost')::INTEGER AS lost,
               count(*) FILTER (WHERE result = 'no_result')::INTEGER AS no_result,
               coalesce(sum(nrr_runs_for), 0)::INTEGER AS nrr_runs_for,
               coalesce(sum(nrr_balls_for), 0)::INTEGER AS nrr_balls_for,
               coalesce(sum(nrr_runs_against), 0)::INTEGER AS nrr_runs_against,
               coalesce(sum(nrr_balls_against), 0)::INTEGER AS nrr_balls_against
        FROM team_matches WHERE in_table GROUP BY ALL
    ),
    abandoned AS (
        SELECT season, franchise_id, count(*)::INTEGER AS abandoned
        FROM abandoned_fixtures GROUP BY ALL
    ),
    league AS (
        SELECT e.*, coalesce(p.won, 0) AS won, coalesce(p.lost, 0) AS lost,
               coalesce(p.no_result, 0) AS no_result, coalesce(a.abandoned, 0) AS abandoned,
               coalesce(p.nrr_runs_for, 0) AS nrr_runs_for,
               coalesce(p.nrr_balls_for, 0) AS nrr_balls_for,
               coalesce(p.nrr_runs_against, 0) AS nrr_runs_against,
               coalesce(p.nrr_balls_against, 0) AS nrr_balls_against
        FROM entrants e
        LEFT JOIN played p USING (season, franchise_id)
        LEFT JOIN abandoned a USING (season, franchise_id)
    ),
    scored AS (
        SELECT *,
               (won + lost + no_result + abandoned)::INTEGER AS played,
               (2 * won + no_result + abandoned)::INTEGER AS points,
               CASE WHEN nrr_balls_for > 0 AND nrr_balls_against > 0
                    THEN round(6 * nrr_runs_for / nrr_balls_for
                               - 6 * nrr_runs_against / nrr_balls_against, 3) END AS nrr
        FROM league
    ),
    playoffs AS (
        SELECT season, franchise_id,
               bool_or(stage = 'Final' AND result = 'won') AS champion,
               bool_or(stage = 'Final' AND result = 'lost') AS runner_up,
               arg_max(stage, match_order) AS last_stage
        FROM team_matches WHERE is_playoff GROUP BY ALL
    )
    SELECT s.season, s.franchise_id, s.team_id, s.team_name, s.played, s.won, s.lost,
           s.no_result, s.abandoned, s.points, s.nrr_runs_for, s.nrr_balls_for,
           s.nrr_runs_against, s.nrr_balls_against, s.nrr,
           row_number() OVER (
               PARTITION BY s.season
               ORDER BY s.points DESC, s.won DESC, s.nrr DESC NULLS LAST, s.franchise_id
           )::INTEGER AS position,
           count(*) OVER (PARTITION BY s.season)::INTEGER AS teams,
           CASE WHEN p.champion THEN 'champion'
                WHEN p.runner_up THEN 'runner_up'
                WHEN p.franchise_id IS NOT NULL THEN 'playoffs'
                ELSE 'league' END AS finish,
           CASE WHEN p.franchise_id IS NOT NULL AND NOT p.champion THEN p.last_stage END
               AS exit_stage
    FROM scored s
    LEFT JOIN playoffs p USING (season, franchise_id)
    ORDER BY s.season, position
"""


def build_team_tables(
    con: duckdb.DuckDBPyConnection,
    tables: LeagueTablesConfig,
    *,
    home_country: str | None = None,
    national_homes: dict[str, list[str]] | None = None,
) -> None:
    """Create the Team Analytics tables from the serving copies of the core tables.

    ``home_country`` limits a league's home grounds to one country (the IPL's
    India); ``national_homes`` maps each national side to the countries it is at
    home in, and makes the competition an international one.
    """
    con.execute("SET VARIABLE home_country = ?", [home_country])
    con.execute("SET VARIABLE national = ?", [national_homes is not None])
    con.execute("CREATE TEMP TABLE home_countries (franchise_id VARCHAR, country VARCHAR)")
    homes = [(team, country) for team, cs in (national_homes or {}).items() for country in cs]
    if homes:
        con.executemany("INSERT INTO home_countries VALUES (?, ?)", homes)
    con.execute("CREATE TEMP TABLE voided_matches (match_id BIGINT)")
    if tables.voided:
        con.executemany(
            "INSERT INTO voided_matches VALUES (?)", [(v.match_id,) for v in tables.voided]
        )
    con.execute("CREATE TEMP TABLE abandoned_fixtures (season INTEGER, franchise_id VARCHAR)")
    if tables.abandoned:
        con.executemany(
            "INSERT INTO abandoned_fixtures VALUES (?, ?)",
            [(f.season, team) for f in tables.abandoned for team in f.teams],
        )
    con.execute(TEAM_MATCHES_SQL)
    con.execute(FORM_SQL)
    con.execute("DROP TABLE team_matches_base")
    con.execute(_phases_sql())
    con.execute(RECORDS_SQL)
    con.execute("DROP TABLE voided_matches")
    con.execute("DROP TABLE abandoned_fixtures")
    con.execute("DROP TABLE home_countries")


@dataclass(frozen=True)
class TableCheck:
    season: int
    problems: list[str]

    @property
    def passed(self) -> bool:
        return not self.problems


def check_league_tables(
    con: duckdb.DuckDBPyConnection, tables: LeagueTablesConfig
) -> list[TableCheck]:
    """Compare computed league tables with the official ones.

    A season is checked only when the data covers its whole league stage (every
    official fixture is either in the data or listed as abandoned), so a partial
    build such as the test fixtures checks nothing.
    """
    checks: list[TableCheck] = []
    for season, official in sorted(tables.seasons.items()):
        rows = con.execute(
            """
            SELECT franchise_id, won, lost, no_result + abandoned AS no_result, points, nrr,
                   position
            FROM team_season_records WHERE season = ? ORDER BY position
            """,
            [season],
        ).fetchall()
        expected_games = sum(r.won + r.lost + r.no_result for r in official)
        actual_games = sum(r[1] + r[2] + r[3] for r in rows)
        if not rows or actual_games != expected_games:
            continue
        problems: list[str] = []
        for position, (want, got) in enumerate(zip(official, rows, strict=False), start=1):
            franchise, won, lost, no_result, points, nrr, _ = got
            if franchise != want.franchise_id:
                problems.append(f"position {position}: {franchise}, official {want.franchise_id}")
                continue
            actual = (won, lost, no_result, points)
            wanted = (want.won, want.lost, want.no_result, want.points)
            if actual != wanted:
                problems.append(f"{franchise}: W-L-NR-Pts {actual}, official {wanted}")
            if nrr is None or abs(float(nrr) - want.nrr) > 0.0005:
                problems.append(f"{franchise}: NRR {nrr}, official {want.nrr:+.3f}")
        if len(rows) != len(official):
            problems.append(f"{len(rows)} teams, official {len(official)}")
        checks.append(TableCheck(season, problems))
    return checks
