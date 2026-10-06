"""The players database: Player Lab tables for every T20 competition and all T20.

Each competition's tables are built exactly as the IPL's are for the serving
database (``criciq_pipelines.players``), from that competition's v1-shaped copy
of the full warehouse. Par is therefore that competition's own rate for the
season and phase: a PSL strike rate is judged against the PSL, a T20I economy
against T20Is. The IPL's tables equal the serving database's.

"All T20" (scope ``T20``) puts a player's T20 cricket together: its rows are the
competitions' rows, each keeping its own par, and only the directory
(``player_index``: role, seasons, latest team) is computed over the union.

Layout:

- ``main`` holds the tables, every one with a ``competition_id`` column (the
  directory has ``scope_id`` instead), plus ``scopes`` describing each scope.
- One schema per scope (``ipl``, ``bbl``, ... and ``t20``) holds views with the
  serving database's table names and columns, restricted to that scope. With
  ``search_path`` set to a scope's schema, the API's Player Lab queries run
  unchanged on any competition. In ``t20`` an innings' ``match_order`` is its
  order across every competition, so "most recent" means the same everywhere.
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

import duckdb

from criciq_pipelines import __version__
from criciq_pipelines.export import copy_core_tables
from criciq_pipelines.players import INDEX_QUERY, PLAYER_TABLES, build_player_tables
from criciq_pipelines.reference import load_competitions
from criciq_pipelines.scope import build_scope

# The formats in the players database so far (ODI and Test follow in V2-5 and V2-6).
FORMATS = ("T20",)
# The scope holding every T20 competition.
ALL_T20 = "T20"
# The colour of teams without a curated one (most associate nations).
NEUTRAL_COLOR = "#7A7A7A"

# Player tables with one row per innings, which also carry the global match order.
_INNINGS_TABLES = ("player_batting_innings", "player_bowling_innings")
# Scope views of these tables come straight from the competitions' rows.
_COMPETITION_TABLES = tuple(t for t in PLAYER_TABLES if t != "player_index")

SCOPES_SQL = """
CREATE TABLE scopes (
    scope_id        VARCHAR PRIMARY KEY,
    schema_name     VARCHAR NOT NULL UNIQUE,
    name            VARCHAR NOT NULL,
    short_name      VARCHAR NOT NULL,
    format          VARCHAR NOT NULL,
    competition_ids VARCHAR[] NOT NULL,
    display_order   INTEGER NOT NULL
)
"""


class PlayerDatabaseError(RuntimeError):
    pass


def export_players(
    warehouse: Path, target: Path, competitions: Sequence[str] | None = None
) -> dict[str, int]:
    """Write the players database for the T20 competitions in the full ``warehouse``
    (or those of ``competitions``) to ``target`` atomically; return row counts."""
    included = _included(warehouse, competitions)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)
    con = duckdb.connect(str(staging))
    try:
        con.execute(f"ATTACH '{warehouse.as_posix()}' AS w (READ_ONLY)")
        with tempfile.TemporaryDirectory(prefix="criciq-players-") as work:
            for position, competition in enumerate(included):
                part = _build_part(warehouse, competition, Path(work))
                _add_part(con, competition, part, first=position == 0)
        _add_shared(con, included)
        con.execute("DETACH w")
        _add_scopes(con, included)
        counts = {
            table: int(con.execute(f"SELECT count(*) FROM main.{table}").fetchone()[0])  # type: ignore[index]
            for table in ("scopes", "players", *PLAYER_TABLES)
        }
        con.execute("CHECKPOINT")
    except BaseException:
        con.close()
        staging.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(staging, target)
    return counts


def _included(warehouse: Path, competitions: Sequence[str] | None) -> list[str]:
    """The T20 competitions with matches in ``warehouse``, in config order."""
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        present = {
            cid
            for (cid,) in con.execute(
                """
                SELECT DISTINCT competition_id FROM matches JOIN competitions USING (competition_id)
                WHERE list_contains(?, format)
                """,
                [list(FORMATS)],
            ).fetchall()
        }
    finally:
        con.close()
    wanted = {c.upper() for c in competitions} if competitions is not None else present
    included = [c.id for c in load_competitions().competitions if c.id in present & wanted]
    if not included:
        raise PlayerDatabaseError(f"no {'/'.join(FORMATS)} matches to build players from")
    return included


def _build_part(warehouse: Path, competition: str, work: Path) -> Path:
    """One competition's Player Lab tables, built from its v1-shaped copy."""
    scope = work / f"{competition.lower()}.duckdb"
    build_scope(warehouse, competition, scope)
    part = work / f"{competition.lower()}-players.duckdb"
    con = duckdb.connect(str(part))
    try:
        con.execute(f"ATTACH '{scope.as_posix()}' AS wh (READ_ONLY)")
        copy_core_tables(con)
        build_player_tables(con)
        con.execute("DETACH wh")
    finally:
        con.close()
    scope.unlink()
    return part


def _add_part(con: duckdb.DuckDBPyConnection, competition: str, part: Path, *, first: bool) -> None:
    """Append one competition's tables, tagged with its id."""
    con.execute(f"ATTACH '{part.as_posix()}' AS part (READ_ONLY)")
    try:
        con.execute("SET VARIABLE competition = ?", [competition])
        con.execute("SET VARIABLE neutral = ?", [NEUTRAL_COLOR])
        sources = {
            table: f"SELECT getvariable('competition') AS competition_id, * FROM part.{table}"
            for table in _COMPETITION_TABLES
        }
        for table in _INNINGS_TABLES:
            sources[table] = f"""
                SELECT getvariable('competition') AS competition_id, p.*, m.global_order
                FROM part.{table} p JOIN w.matches m USING (match_id)
                ORDER BY p.player_id, m.global_order, p.innings_no
            """
        sources["player_index"] = (
            "SELECT getvariable('competition') AS scope_id, * FROM part.player_index"
        )
        # Every team tag needs a colour; sides without a curated one get neutral grey.
        sources["franchises"] = (
            "SELECT * REPLACE (coalesce(primary_color, getvariable('neutral')) AS primary_color) "
            "FROM part.franchises"
        )
        sources["venues"] = "SELECT * FROM part.venues"
        for table, sql in sources.items():
            if first:
                con.execute(f"CREATE TABLE main.{table} AS {sql}")
            else:
                con.execute(f"INSERT INTO main.{table} {sql}")
    finally:
        con.execute("DETACH part")
    part.unlink()


def _add_shared(con: duckdb.DuckDBPyConnection, included: list[str]) -> None:
    """Tables every scope reads: the full warehouse's rows for the included competitions."""
    con.execute("SET VARIABLE included = ?", [included])
    config = {c.id: c for c in load_competitions().competitions}
    con.execute(
        "SET VARIABLE spanning = ?", [[c for c in included if config[c].season_spans_new_year]]
    )
    con.execute(
        """
        CREATE TABLE main.competitions AS
        SELECT competition_id, name, short_name, format, gender, team_type
        FROM w.competitions WHERE list_contains(getvariable('included'), competition_id);

        -- A season's name: Cricsheet's "2023/24" where seasons span the new year
        -- (the BBL), else the year (Cricsheet calls IPL 2008 "2007/08").
        CREATE TABLE main.seasons AS
        SELECT s.season_id, s.competition_id, s.year, s.cricsheet_label, s.impact_player_rule,
               CASE WHEN list_contains(getvariable('spanning')::VARCHAR[], s.competition_id)
                    THEN s.cricsheet_label ELSE s.year::VARCHAR END AS label,
               s.start_date, s.end_date
        FROM w.seasons s WHERE list_contains(getvariable('included'), s.competition_id)
        ORDER BY s.competition_id, s.year;

        CREATE TABLE main.matches AS
        SELECT match_id, competition_id, season_id, match_order, global_order, match_date
        FROM w.matches WHERE list_contains(getvariable('included'), competition_id)
        ORDER BY global_order;

        CREATE TABLE main.innings AS
        SELECT match_id, innings_no, is_super_over FROM w.innings
        WHERE match_id IN (SELECT match_id FROM main.matches) ORDER BY ALL;

        CREATE TABLE main.wickets AS
        SELECT match_id, innings_no, seq_no, wicket_no, player_out_id, kind, is_dismissal,
               bowler_credited, bowler_id
        FROM w.wickets WHERE match_id IN (SELECT match_id FROM main.matches) ORDER BY ALL;

        CREATE TABLE main.players AS
        SELECT player_id, name, full_name, country, date_of_birth, batting_hand,
               bowling_arm, bowling_type, bowling_style
        FROM w.players
        WHERE player_id IN (SELECT player_id FROM main.player_index)
        ORDER BY player_id;
        """
    )
    # Venues came with each competition; a ground used by several appears once.
    con.execute(
        "CREATE TABLE main.venues_once AS SELECT DISTINCT * FROM main.venues ORDER BY venue_id"
    )
    con.execute("DROP TABLE main.venues")
    con.execute("ALTER TABLE main.venues_once RENAME TO venues")
    meta = dict(con.execute("SELECT key, value FROM w.meta").fetchall())
    con.execute("CREATE TABLE main.meta (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
    con.executemany(
        "INSERT INTO main.meta VALUES (?, ?)",
        [
            ["data_version", meta["data_version"]],
            ["pipeline_version", __version__],
            ["built_at", dt.datetime.now(dt.UTC).isoformat(timespec="seconds")],
            ["competitions", ",".join(included)],
        ],
    )


def _add_scopes(con: duckdb.DuckDBPyConnection, included: list[str]) -> None:
    """The scopes table and one schema of views per scope (see the module docstring)."""
    con.execute(SCOPES_SQL)
    config = {c.id: c for c in load_competitions().competitions}
    scopes = [
        (cid, cid.lower(), config[cid].name, config[cid].short_name, config[cid].format, [cid])
        for cid in included
    ]
    scopes.append((ALL_T20, ALL_T20.lower(), "All T20 cricket", "All T20", "T20", included))
    for order, (scope_id, schema, name, short_name, fmt, members) in enumerate(scopes):
        con.execute(
            "INSERT INTO scopes VALUES (?, ?, ?, ?, ?, ?, ?)",
            [scope_id, schema, name, short_name, fmt, members, order],
        )
        _scope_views(con, scope_id, schema, members)
    # The All T20 directory: computed over the union, through its scope's views.
    con.execute(f"SET search_path = '{ALL_T20.lower()},main'")
    try:
        con.execute(f"CREATE TEMP TABLE all_index AS {INDEX_QUERY}")
    finally:
        con.execute("RESET search_path")
    con.execute(f"INSERT INTO main.player_index SELECT '{ALL_T20}', * FROM all_index")
    con.execute("DROP TABLE all_index")


def _scope_views(
    con: duckdb.DuckDBPyConnection, scope_id: str, schema: str, members: list[str]
) -> None:
    within = "competition_id IN (" + ", ".join(f"'{m}'" for m in members) + ")"
    single = len(members) == 1
    # The order innings are listed in: per competition, or across all of them.
    order = "match_order" if single else "global_order AS match_order"
    views = {
        "competitions": f"SELECT * FROM main.competitions WHERE {within}",
        "seasons": f"SELECT * EXCLUDE (label) FROM main.seasons WHERE {within}",
        "franchises": (
            f"SELECT * FROM main.franchises WHERE {within}"
            if single
            else f"""SELECT franchise_id, any_value(competition_id) AS competition_id,
                        any_value(name) AS name, any_value(primary_color) AS primary_color,
                        any_value(secondary_color) AS secondary_color,
                        min(first_season) AS first_season, max(last_season) AS last_season,
                        bool_or(is_active) AS is_active
                 FROM main.franchises WHERE {within} GROUP BY franchise_id"""
        ),
        "matches": (
            f"SELECT match_id, competition_id, season_id, {order}, match_date "
            f"FROM main.matches WHERE {within}"
        ),
        "player_index": (
            f"SELECT * EXCLUDE (scope_id) FROM main.player_index WHERE scope_id = '{scope_id}'"
        ),
    }
    for table in _COMPETITION_TABLES:
        if table in _INNINGS_TABLES:
            views[table] = (
                f"SELECT * EXCLUDE (competition_id, match_order, global_order), {order} "
                f"FROM main.{table} WHERE {within}"
            )
        else:
            views[table] = f"SELECT * EXCLUDE (competition_id) FROM main.{table} WHERE {within}"
    con.execute(f"CREATE SCHEMA {schema}")
    for name, sql in views.items():
        con.execute(f"CREATE VIEW {schema}.{name} AS {sql}")
