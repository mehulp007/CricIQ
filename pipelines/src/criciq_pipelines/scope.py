"""Per-competition warehouses in the v1 shape.

The full warehouse holds every competition. Everything built before v2 (the
serving export, the models, the reports) reads one competition from a database
whose tables have exactly the v1 columns: ``franchises`` rather than ``teams``,
and no Test-only columns. This module writes that copy for one competition, so
those consumers keep producing identical output while they are made
multi-competition one by one.

A copy can also hold several competitions (the pooled T20 copy the models train
on): ``match_order`` is then the order across all of them, and every other
table keeps each competition's rows unchanged.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Sequence
from pathlib import Path

import duckdb

from criciq_pipelines import __version__

# v1 columns of every table, in order: the contract the scoped copy keeps.
_MATCH_COLUMNS = (
    "match_id, competition_id, season_id, match_order, match_date, end_date, match_number, "
    "stage, is_playoff, venue_id, team1_id, team2_id, toss_winner_id, toss_decision, "
    "outcome_type, winner_id, win_by_runs, win_by_wickets, win_method, decided_by_super_over, "
    "scheduled_overs, balls_per_over, player_of_match_ids, cricsheet_version"
)
_INNINGS_COLUMNS = (
    "match_id, innings_no, batting_team_id, bowling_team_id, is_super_over, target_runs, "
    "target_overs, target_balls, runs, wickets, legal_balls, extras, absent_hurt_ids, "
    "miscounted_overs"
)


class ScopeError(RuntimeError):
    pass


def build_scope(
    warehouse: Path, competition_id: str | Sequence[str], target: Path
) -> dict[str, int]:
    """Copy one competition (or several) from the full warehouse into ``target`` (v1 shape)."""
    ids = [competition_id] if isinstance(competition_id, str) else list(competition_id)
    if not ids:
        raise ScopeError("no competition to copy")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)
    con = duckdb.connect(str(staging))
    try:
        con.execute(f"ATTACH '{warehouse.as_posix()}' AS w (READ_ONLY)")
        found = {
            cid
            for (cid,) in con.execute(
                "SELECT competition_id FROM w.competitions WHERE list_contains(?, competition_id)",
                [ids],
            ).fetchall()
        }
        if missing := [c for c in ids if c not in found]:
            raise ScopeError(f"competition {missing[0]!r} is not in {warehouse}")
        con.execute("SET VARIABLE competitions = ?", [ids])
        # One competition keeps its own match order; several are ordered across all of them.
        order = (
            "match_order"
            if len(ids) == 1
            else "(row_number() OVER (ORDER BY global_order))::INTEGER AS match_order"
        )
        columns = _MATCH_COLUMNS.replace("match_order", order, 1)
        con.execute(
            f"""
            CREATE TABLE competitions AS
            SELECT competition_id, name, short_name, format, gender, team_type
            FROM w.competitions WHERE list_contains(getvariable('competitions'), competition_id)
            ORDER BY competition_id;

            CREATE TABLE seasons AS
            SELECT season_id, competition_id, year, cricsheet_label, impact_player_rule
            FROM w.seasons WHERE list_contains(getvariable('competitions'), competition_id)
            ORDER BY year, competition_id;

            CREATE TABLE franchises AS
            SELECT t.team_id AS franchise_id, ct.competition_id, t.name,
                   t.primary_color, t.secondary_color,
                   ct.first_season, ct.last_season, ct.is_active
            FROM w.competition_teams ct JOIN w.teams t USING (team_id)
            WHERE list_contains(getvariable('competitions'), ct.competition_id)
            ORDER BY t.team_id, ct.competition_id;

            CREATE TABLE team_seasons AS
            SELECT ts.team_season_id, ts.team_id AS franchise_id, ts.season_id, ts.display_name
            FROM w.team_seasons ts JOIN seasons s USING (season_id)
            ORDER BY ts.team_season_id;

            CREATE TABLE matches AS
            SELECT {columns} FROM w.matches
            WHERE list_contains(getvariable('competitions'), competition_id) ORDER BY match_id;

            CREATE TABLE venues AS
            SELECT venue_id, name, city, country, notes FROM w.venues
            WHERE is_curated OR venue_id IN (SELECT venue_id FROM matches)
            ORDER BY venue_id;

            CREATE TABLE venue_aliases AS
            SELECT raw_name, venue_id FROM w.venue_aliases
            WHERE venue_id IN (SELECT venue_id FROM venues)
              -- A curated ground keeps its curated names only; an added ground keeps all.
              AND (is_curated OR venue_id IN (SELECT venue_id FROM w.venues WHERE NOT is_curated))
            ORDER BY raw_name;

            CREATE TABLE innings AS
            SELECT {_INNINGS_COLUMNS} FROM w.innings
            WHERE match_id IN (SELECT match_id FROM matches) ORDER BY match_id, innings_no;

            CREATE TABLE deliveries AS
            SELECT * FROM w.deliveries
            WHERE match_id IN (SELECT match_id FROM matches)
            ORDER BY match_id, innings_no, seq_no;

            CREATE TABLE wickets AS
            SELECT * FROM w.wickets WHERE match_id IN (SELECT match_id FROM matches) ORDER BY ALL;

            CREATE TABLE match_players AS
            SELECT * FROM w.match_players
            WHERE match_id IN (SELECT match_id FROM matches)
            ORDER BY match_id, team_season_id, list_position;

            CREATE TABLE substitutions AS
            SELECT * FROM w.substitutions
            WHERE match_id IN (SELECT match_id FROM matches) ORDER BY ALL;

            CREATE TABLE players AS
            SELECT * FROM w.players WHERE player_id IN (
                SELECT player_id FROM match_players
                UNION SELECT batter_id FROM deliveries
                UNION SELECT non_striker_id FROM deliveries
                UNION SELECT bowler_id FROM deliveries
                UNION SELECT player_out_id FROM wickets
                UNION SELECT unnest(fielder_ids) FROM wickets
                UNION SELECT player_in_id FROM substitutions
                UNION SELECT player_out_id FROM substitutions
                UNION SELECT unnest(player_of_match_ids) FROM matches
                UNION SELECT unnest(absent_hurt_ids) FROM innings
            ) ORDER BY player_id;

            CREATE TABLE player_identifiers AS
            SELECT * FROM w.player_identifiers
            WHERE player_id IN (SELECT player_id FROM players) ORDER BY ALL;

            CREATE TABLE meta AS
            SELECT key, value FROM w.meta
            WHERE key NOT IN ('competitions', 'built_at', 'pipeline_version');
            """
        )
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ["competition_id", ",".join(ids)],
                ["pipeline_version", __version__],
                ["built_at", dt.datetime.now(dt.UTC).isoformat(timespec="seconds")],
            ],
        )
        counts = {
            table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]
            for table in (
                "competitions",
                "seasons",
                "franchises",
                "team_seasons",
                "venues",
                "venue_aliases",
                "players",
                "player_identifiers",
                "matches",
                "innings",
                "deliveries",
                "wickets",
                "match_players",
                "substitutions",
            )
        }
        con.execute("DETACH w")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    os.replace(staging, target)
    return counts
