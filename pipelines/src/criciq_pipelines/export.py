"""Export the read-only serving database the API ships with.

The serving database is a slim copy of the warehouse (only what the API reads)
plus precomputed, presentation-ready tables such as ``match_summaries``, so
request-time queries stay simple and fast. See docs/adr/0001.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

from criciq_pipelines.events import EVENT_TABLES, build_event_tables, check_events
from criciq_pipelines.players import PLAYER_TABLES, build_player_tables
from criciq_pipelines.reference import (
    LeagueTablesConfig,
    load_competitions,
    load_events,
    load_league_tables,
    load_teams,
)
from criciq_pipelines.simulation import SIMULATION_TABLES, build_simulation_tables
from criciq_pipelines.teams import TEAM_TABLES, build_team_tables, check_league_tables

# The colour of teams without a curated one (most associate nations).
NEUTRAL_COLOR = "#7A7A7A"

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

# Every data update (criciq_pipelines.sync) of the served competitions, newest first.
DATA_UPDATES_SQL = """
CREATE TABLE data_updates (
    run_id              INTEGER NOT NULL,
    updated_at          TIMESTAMP NOT NULL,
    kind                VARCHAR NOT NULL,
    competition_id      VARCHAR NOT NULL,
    new_matches         INTEGER NOT NULL,
    corrected_matches   INTEGER NOT NULL,
    withdrawn_matches   INTEGER NOT NULL,
    quarantined_matches INTEGER NOT NULL
)
"""

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
last_super_over AS (
    -- The final pair of super-over innings: level means boundaries decided it (the 2019
    -- World Cup final, IPL 2014 KKR v RR).
    SELECT match_id, bool_and(runs = max_runs) AND count(*) = 2 AS level
    FROM (
        SELECT match_id, runs, max(runs) OVER (PARTITION BY match_id) AS max_runs,
               row_number() OVER (PARTITION BY match_id ORDER BY innings_no DESC) AS rank
        FROM innings WHERE is_super_over
    )
    WHERE rank <= 2
    GROUP BY match_id
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
        -- Ties without a winner, and the bowl-outs that settled ties before super overs.
        WHEN m.outcome_type = 'tie' AND tw.display_name IS NULL THEN 'Match tied'
            || CASE WHEN m.win_method IS NOT NULL THEN ' (' || m.win_method || ')' ELSE '' END
        WHEN m.outcome_type = 'tie' AND m.decided_by_super_over AND so.level
            THEN 'Match tied (' || tw.display_name || ' won on boundaries after a tied super over)'
        WHEN m.outcome_type = 'tie' AND m.decided_by_super_over
            THEN 'Match tied (' || tw.display_name || ' won the super over)'
        WHEN m.outcome_type = 'tie' THEN 'Match tied (' || tw.display_name || ' won the bowl-out)'
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
LEFT JOIN last_super_over so ON so.match_id = m.match_id
ORDER BY m.match_order
"""

# Test matches (a serving database of Tests only): every innings of each side, and
# results that limited-overs cricket does not have (draws, innings victories).
TEST_SUMMARIES_SQL = f"""
CREATE OR REPLACE TABLE match_summaries AS
WITH sides AS (
    SELECT i.match_id, i.batting_team_id,
           list({{
               'innings_no': i.innings_no, 'runs': i.runs, 'wickets': i.wickets,
               'overs': {_OVERS.format(b="i.legal_balls")}, 'declared': i.declared,
               'follow_on': i.follow_on, 'forfeited': i.forfeited
           }} ORDER BY i.innings_no) AS innings
    FROM innings i
    GROUP BY i.match_id, i.batting_team_id
)
SELECT s.* REPLACE (
           CASE
               WHEN m.outcome_type = 'draw' THEN 'Match drawn'
               WHEN m.outcome_type = 'tie' THEN 'Match tied'
               WHEN m.win_by_innings IS NOT NULL THEN
                   s.winner_name || ' won by an innings and ' || m.win_by_runs
                   || CASE WHEN m.win_by_runs = 1 THEN ' run' ELSE ' runs' END
               ELSE s.result_text
           END AS result_text
       ),
       m.win_by_innings IS NOT NULL AS won_by_innings,
       coalesce(a.innings, []) AS team_a_innings,
       coalesce(b.innings, []) AS team_b_innings
FROM match_summaries s
JOIN matches m USING (match_id)
LEFT JOIN sides a ON a.match_id = s.match_id AND a.batting_team_id = s.team_a_id
LEFT JOIN sides b ON b.match_id = s.match_id AND b.batting_team_id = s.team_b_id
ORDER BY s.match_order
"""


class LeagueTableMismatchError(RuntimeError):
    pass


class EventResultMismatchError(RuntimeError):
    pass


def copy_core_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Copy the tables the serving database keeps from the attached warehouse ``wh``."""
    for table in COPIED_TABLES:
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM wh.{table}")
    # Every team gets a colour (the IPL's all have curated ones).
    con.execute(
        """
        UPDATE franchises
        SET primary_color = coalesce(primary_color, $neutral),
            secondary_color = coalesce(secondary_color, $neutral)
        WHERE primary_color IS NULL OR secondary_color IS NULL
        """,
        {"neutral": NEUTRAL_COLOR},
    )
    con.execute(
        """
        CREATE TABLE players AS
        SELECT player_id, name, full_name, country, date_of_birth, batting_hand,
               bowling_arm, bowling_type, bowling_style
        FROM wh.players
        """
    )


def export_serving(
    warehouse: Path,
    target: Path,
    updates: Path | None = None,
    *,
    events: Path | None = None,
) -> dict[str, int]:
    """Write the serving database to ``target`` atomically; return row counts.

    Fails if a computed league table differs from the official one for any season
    the data fully covers. The league-tables config (official tables, abandoned
    fixtures, voided matches) is the IPL's; other competitions are built without
    it. ``updates`` is the sync's ingest database: its record of data updates for
    the served competitions goes into ``data_updates``. ``events`` is the full
    warehouse, whose Cricsheet event names and groups make a national
    competition's series and tournaments (``criciq_pipelines.events``); building
    them fails if a known result in ``config/events.yaml`` comes out differently.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)

    con = duckdb.connect(str(staging))
    try:
        con.execute(f"ATTACH '{warehouse.as_posix()}' AS wh (READ_ONLY)")
        copy_core_tables(con)
        con.execute(MATCH_SUMMARIES_SQL)
        formats = {r[0] for r in con.execute("SELECT DISTINCT format FROM competitions").fetchall()}
        if formats == {"Test"}:
            con.execute(TEST_SUMMARIES_SQL)
        con.execute("DETACH wh")
        con.execute(DATA_UPDATES_SQL)
        if updates is not None:
            con.execute(f"ATTACH '{updates.as_posix()}' AS ingest (READ_ONLY)")
            con.execute(
                """
                INSERT INTO data_updates
                SELECT run_id, updated_at, kind, competition_id, new_matches,
                       corrected_matches, withdrawn_matches, quarantined_matches
                FROM ingest.data_updates
                WHERE competition_id IN (SELECT competition_id FROM competitions)
                ORDER BY run_id DESC, competition_id
                """
            )
            con.execute("DETACH ingest")
        build_player_tables(con)
        served = {r[0] for r in con.execute("SELECT competition_id FROM competitions").fetchall()}
        league_tables = load_league_tables() if served == {"IPL"} else LeagueTablesConfig()
        # How the API names seasons: "2023/24" where they span the new year, else the year.
        configured = load_competitions()
        spans = any(configured.get(c).season_spans_new_year for c in served)
        con.execute("INSERT INTO meta VALUES ('season_spans_new_year', ?)", [str(spans).lower()])
        competitions = [configured.get(c) for c in sorted(served)]
        national = [c for c in competitions if c.team_type == "national"]
        build_team_tables(
            con,
            league_tables,
            home_country=competitions[0].home_country if len(competitions) == 1 else None,
            national_homes=(
                {t.id: t.home_in for c in national for t in load_teams(c.teams).teams}
                if national
                else None
            ),
        )
        build_simulation_tables(con)
        event_tables: tuple[str, ...] = ()
        if events is not None and len(national) == 1 and len(competitions) == 1:
            competition = national[0].id
            con.execute(f"ATTACH '{events.as_posix()}' AS ev (READ_ONLY)")
            config = load_events()
            build_event_tables(con, competition, config)
            con.execute("DETACH ev")
            wrong = [c for c in check_events(con, competition, config) if not c.passed]
            if wrong:
                details = "; ".join(f"{c.description}: {', '.join(c.problems)}" for c in wrong)
                raise EventResultMismatchError(f"events differ from known results: {details}")
            event_tables = EVENT_TABLES
        failed = [c for c in check_league_tables(con, league_tables) if not c.passed]
        if failed:
            details = "; ".join(f"{c.season}: {', '.join(c.problems)}" for c in failed)
            raise LeagueTableMismatchError(
                f"league tables differ from the official ones: {details}"
            )
        counts = {
            table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]
            for table in (
                *COPIED_TABLES,
                "players",
                "match_summaries",
                "data_updates",
                *PLAYER_TABLES,
                *TEAM_TABLES,
                *SIMULATION_TABLES,
                *event_tables,
            )
        }
        con.execute("CHECKPOINT")
    except BaseException:
        con.close()
        staging.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(staging, target)
    return counts
