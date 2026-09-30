"""Build the normalized DuckDB warehouse from interim Parquet + reference config.

The build is all-or-nothing: it writes to a temporary file and only replaces
the live warehouse once every table has loaded under the schema's key,
reference and domain constraints.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import duckdb
import pyarrow as pa

from criciq_pipelines import __version__
from criciq_pipelines.reference import (
    CompetitionsConfig,
    FranchisesConfig,
    VenuesConfig,
    load_competitions,
    load_franchises,
    load_venues,
)

COMPETITION_ID = "IPL"

# Dismissal kinds credited to the bowler. Run outs, obstructing the field and
# retirements are not.
BOWLER_CREDITED_KINDS = (
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket",
)
# "retired hurt" is not a dismissal: the batter may return and it does not
# count toward the team's wickets. "retired out" does count.
NON_DISMISSAL_KINDS = ("retired hurt", "retired not out")


class WarehouseBuildError(RuntimeError):
    """Raised when inputs cannot be mapped onto the warehouse model."""


@dataclass(frozen=True)
class BuildInputs:
    interim_dir: Path
    people_csv: Path
    data_version: str
    attributes_csv: Path | None = None
    config_dir: Path | None = None


def build_warehouse(inputs: BuildInputs, target: Path) -> dict[str, int]:
    """Build the warehouse at ``target`` and return row counts per table."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)

    competitions = load_competitions(inputs.config_dir)
    franchises = load_franchises(inputs.config_dir)
    venues = load_venues(inputs.config_dir)

    con = duckdb.connect(str(staging))
    try:
        con.execute(resources.files("criciq_pipelines").joinpath("sql/schema.sql").read_text())
        _register_interim(con, inputs.interim_dir)
        _load_reference(con, competitions, franchises, venues)
        _load_players(con, inputs.people_csv, inputs.attributes_csv)
        _load_matches(con)
        _load_innings_and_deliveries(con)
        _load_participation(con)
        _write_meta(con, inputs)
        counts = {
            table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]
            for table in _TABLES
        }
        con.execute("CHECKPOINT")
    finally:
        con.close()
    os.replace(staging, target)
    return counts


_TABLES = (
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


def _register_interim(con: duckdb.DuckDBPyConnection, interim_dir: Path) -> None:
    for name in (
        "matches",
        "innings",
        "deliveries",
        "wickets",
        "replacements",
        "match_players",
        "registry",
    ):
        path = (interim_dir / f"{name}.parquet").as_posix()
        con.execute(f"CREATE TEMP VIEW raw_{name} AS SELECT * FROM read_parquet('{path}')")


# --------------------------------------------------------------------------- reference


def _load_reference(
    con: duckdb.DuckDBPyConnection,
    competitions: CompetitionsConfig,
    franchises: FranchisesConfig,
    venues: VenuesConfig,
) -> None:
    competition = competitions.get(COMPETITION_ID)
    con.execute(
        "INSERT INTO competitions VALUES (?, ?, ?, ?, ?, ?)",
        [
            competition.id,
            competition.name,
            competition.short_name,
            competition.format,
            competition.gender,
            competition.team_type,
        ],
    )

    unexpected = con.execute(
        "SELECT DISTINCT event_name FROM raw_matches WHERE event_name <> ?",
        [competition.cricsheet.event_name],
    ).fetchall()
    if unexpected:
        raise WarehouseBuildError(f"unexpected events in archive: {unexpected}")

    impact_from = competition.rules.impact_player_from
    con.execute(
        """
        INSERT INTO seasons
        SELECT ? || '-' || year, ?, year, any_value(season_label),
               coalesce(year >= ?, false)
        FROM (SELECT year(match_date) AS year, season_label FROM raw_matches)
        GROUP BY year ORDER BY year
        """,
        [competition.id, competition.id, impact_from],
    )

    con.executemany(
        "INSERT INTO franchises VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            [
                f.id,
                competition.id,
                f.name,
                f.colors.primary,
                f.colors.secondary,
                f.first_season,
                f.last_season,
                f.last_season is None,
            ]
            for f in franchises.franchises
        ],
    )

    # Resolve every (season, raw team name) pair through the config so that an
    # unknown or out-of-range name fails the build with a precise message.
    pairs = con.execute(
        """
        SELECT DISTINCT year(m.match_date) AS year, t.team
        FROM raw_matches m,
             (SELECT match_id, team1 AS team FROM raw_matches
              UNION SELECT match_id, team2 FROM raw_matches) t
        WHERE t.match_id = m.match_id
        ORDER BY 1, 2
        """
    ).fetchall()
    team_rows = []
    for year, team in pairs:
        try:
            franchise = franchises.resolve(team, year)
        except LookupError as exc:
            raise WarehouseBuildError(str(exc)) from None
        team_rows.append([f"{franchise.id}-{year}", franchise.id, f"{competition.id}-{year}", team])
    con.executemany("INSERT INTO team_seasons VALUES (?, ?, ?, ?)", team_rows)
    con.execute(
        """
        CREATE TEMP TABLE team_map AS
        SELECT s.year AS year, t.display_name AS raw_name, t.team_season_id
        FROM team_seasons t JOIN seasons s USING (season_id)
        """
    )

    con.executemany(
        "INSERT INTO venues VALUES (?, ?, ?, ?, ?)",
        [[v.id, v.name, v.city, v.country, v.notes] for v in venues.venues],
    )
    con.executemany(
        "INSERT INTO venue_aliases VALUES (?, ?)", [list(p) for p in venues.alias_map().items()]
    )
    unmapped = con.execute(
        """
        SELECT DISTINCT venue_raw FROM raw_matches
        WHERE venue_raw NOT IN (SELECT raw_name FROM venue_aliases) ORDER BY 1
        """
    ).fetchall()
    if unmapped:
        names = ", ".join(repr(u[0]) for u in unmapped)
        raise WarehouseBuildError(f"unmapped venues (add to config/venues.yaml): {names}")


# --------------------------------------------------------------------------- players

_ATTRIBUTE_COLUMNS = (
    "player_id",
    "full_name",
    "date_of_birth",
    "country",
    "batting_hand",
    "bowling_arm",
    "bowling_type",
    "bowling_style",
    "source",
)


def _load_players(
    con: duckdb.DuckDBPyConnection, people_csv: Path, attributes_csv: Path | None
) -> None:
    con.execute(
        f"""
        CREATE TEMP TABLE people AS
        SELECT * FROM read_csv('{people_csv.as_posix()}', all_varchar = true, header = true)
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE player_ids AS
        SELECT DISTINCT player_id FROM (
            SELECT player_id FROM raw_match_players
            UNION ALL SELECT batter_id FROM raw_deliveries
            UNION ALL SELECT non_striker_id FROM raw_deliveries
            UNION ALL SELECT bowler_id FROM raw_deliveries
            UNION ALL SELECT player_out_id FROM raw_wickets
            UNION ALL SELECT unnest(fielder_ids) FROM raw_wickets
            UNION ALL SELECT player_in_id FROM raw_replacements
            UNION ALL SELECT player_out_id FROM raw_replacements
            UNION ALL SELECT unnest(player_of_match_ids) FROM raw_matches
            UNION ALL SELECT unnest(absent_hurt_ids) FROM raw_innings
        ) WHERE player_id IS NOT NULL
        """
    )
    missing = con.execute(
        "SELECT player_id FROM player_ids WHERE player_id NOT IN (SELECT identifier FROM people)"
    ).fetchall()
    if missing:
        raise WarehouseBuildError(
            f"{len(missing)} player ids missing from people.csv: {missing[:5]}"
        )

    if attributes_csv is not None and attributes_csv.exists():
        columns = ", ".join(f"'{c}': 'VARCHAR'" for c in _ATTRIBUTE_COLUMNS)
        con.execute(
            f"""
            CREATE TEMP TABLE attrs AS
            SELECT * FROM read_csv('{attributes_csv.as_posix()}', header = true,
                                   columns = {{{columns}}})
            """
        )
    else:
        empty = pa.table({c: pa.array([], pa.string()) for c in _ATTRIBUTE_COLUMNS})
        con.register("attrs_empty", empty)
        con.execute("CREATE TEMP TABLE attrs AS SELECT * FROM attrs_empty")

    con.execute(
        """
        INSERT INTO players
        SELECT p.identifier, p.name, coalesce(p.unique_name, p.name),
               nullif(a.full_name, ''), try_cast(nullif(a.date_of_birth, '') AS DATE),
               nullif(a.country, ''), nullif(a.batting_hand, ''), nullif(a.bowling_arm, ''),
               nullif(a.bowling_type, ''), nullif(a.bowling_style, ''), nullif(a.source, '')
        FROM player_ids i
        JOIN people p ON p.identifier = i.player_id
        LEFT JOIN attrs a ON a.player_id = i.player_id
        ORDER BY p.identifier
        """
    )
    key_columns = [
        row[0]
        for row in con.execute(
            "SELECT column_name FROM (DESCRIBE people) WHERE column_name LIKE 'key\\_%' ESCAPE '\\'"
        ).fetchall()
    ]
    for column in key_columns:
        source = column.removeprefix("key_")
        con.execute(
            f"""
            INSERT INTO player_identifiers
            SELECT identifier, '{source}', "{column}" FROM people
            WHERE identifier IN (SELECT player_id FROM player_ids)
              AND "{column}" IS NOT NULL AND "{column}" <> ''
            """
        )


# --------------------------------------------------------------------------- matches


def _load_matches(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        INSERT INTO matches
        SELECT
            m.match_id,
            '{COMPETITION_ID}',
            '{COMPETITION_ID}-' || year(m.match_date),
            row_number() OVER (ORDER BY m.match_date, m.match_number NULLS LAST, m.match_id),
            m.match_date,
            m.end_date,
            m.match_number,
            coalesce(m.stage, 'League'),
            m.stage IS NOT NULL,
            va.venue_id,
            t1.team_season_id,
            t2.team_season_id,
            tw.team_season_id,
            m.toss_decision,
            CASE
                WHEN m.outcome_result = 'tie' THEN 'tie'
                WHEN m.outcome_result = 'no result' THEN 'no_result'
                WHEN m.outcome_winner IS NOT NULL THEN 'win'
            END,
            coalesce(w.team_season_id, el.team_season_id),
            m.outcome_by_runs,
            m.outcome_by_wickets,
            m.outcome_method,
            m.outcome_eliminator IS NOT NULL,
            m.scheduled_overs,
            m.balls_per_over,
            m.player_of_match_ids,
            m.cricsheet_version
        FROM raw_matches m
        JOIN venue_aliases va ON va.raw_name = m.venue_raw
        JOIN team_map t1 ON t1.year = year(m.match_date) AND t1.raw_name = m.team1
        JOIN team_map t2 ON t2.year = year(m.match_date) AND t2.raw_name = m.team2
        LEFT JOIN team_map tw ON tw.year = year(m.match_date) AND tw.raw_name = m.toss_winner
        LEFT JOIN team_map w ON w.year = year(m.match_date) AND w.raw_name = m.outcome_winner
        LEFT JOIN team_map el ON el.year = year(m.match_date) AND el.raw_name = m.outcome_eliminator
        ORDER BY m.match_id
        """
    )
    loaded, extracted = con.execute(
        "SELECT (SELECT count(*) FROM matches), (SELECT count(*) FROM raw_matches)"
    ).fetchone()  # type: ignore[misc]
    if loaded != extracted:
        raise WarehouseBuildError(f"only {loaded} of {extracted} matches could be mapped")


def _load_innings_and_deliveries(con: duckdb.DuckDBPyConnection) -> None:
    non_dismissal = ", ".join(f"'{k}'" for k in NON_DISMISSAL_KINDS)
    credited = ", ".join(f"'{k}'" for k in BOWLER_CREDITED_KINDS)
    con.execute(
        f"""
        CREATE TEMP TABLE innings_teams AS
        SELECT i.match_id, i.innings_no,
               bat.team_season_id AS batting_team_id,
               CASE WHEN bat.team_season_id = m.team1_id THEN m.team2_id ELSE m.team1_id END
                   AS bowling_team_id
        FROM raw_innings i
        JOIN matches m USING (match_id)
        JOIN team_map bat ON bat.year = year(m.match_date) AND bat.raw_name = i.team;

        CREATE TEMP TABLE delivery_dismissals AS
        SELECT match_id, innings_no, seq_no, count(*) AS dismissals
        FROM raw_wickets WHERE kind NOT IN ({non_dismissal})
        GROUP BY ALL;

        INSERT INTO innings
        SELECT i.match_id, i.innings_no, t.batting_team_id, t.bowling_team_id, i.is_super_over,
               i.target_runs, i.target_overs,
               CASE WHEN i.target_overs IS NOT NULL THEN
                   (floor(i.target_overs) * m.balls_per_over
                    + round((i.target_overs - floor(i.target_overs)) * 10))::INTEGER
               END,
               coalesce(agg.runs, 0), coalesce(agg.wickets, 0), coalesce(agg.legal_balls, 0),
               coalesce(agg.extras, 0), i.absent_hurt_ids, i.miscounted_overs_json
        FROM raw_innings i
        JOIN innings_teams t USING (match_id, innings_no)
        JOIN matches m USING (match_id)
        LEFT JOIN (
            SELECT d.match_id, d.innings_no, sum(d.runs_total) AS runs,
                   sum(coalesce(w.dismissals, 0)) AS wickets,
                   max(d.legal_ball_no) AS legal_balls, sum(d.runs_extras) AS extras
            FROM raw_deliveries d
            LEFT JOIN delivery_dismissals w USING (match_id, innings_no, seq_no)
            GROUP BY ALL
        ) agg USING (match_id, innings_no)
        ORDER BY i.match_id, i.innings_no;

        INSERT INTO deliveries
        SELECT d.match_id, d.innings_no, d.seq_no, d.over_no, d.ball_label, d.legal_ball_no,
               d.is_legal, t.batting_team_id, t.bowling_team_id,
               d.batter_id, d.non_striker_id, d.bowler_id,
               d.runs_batter, d.runs_extras, d.runs_total,
               d.runs_batter = 4 AND NOT d.non_boundary,
               d.runs_batter = 6 AND NOT d.non_boundary,
               d.extras_wides, d.extras_noballs, d.extras_byes, d.extras_legbyes, d.extras_penalty,
               coalesce(w.dismissals, 0) > 0,
               sum(d.runs_total) OVER innings_so_far,
               sum(coalesce(w.dismissals, 0)) OVER innings_so_far,
               d.has_review
        FROM raw_deliveries d
        JOIN innings_teams t USING (match_id, innings_no)
        LEFT JOIN delivery_dismissals w USING (match_id, innings_no, seq_no)
        WINDOW innings_so_far AS (PARTITION BY d.match_id, d.innings_no ORDER BY d.seq_no)
        ORDER BY d.match_id, d.innings_no, d.seq_no;

        INSERT INTO wickets
        SELECT w.match_id, w.innings_no, w.seq_no, w.wicket_no, w.player_out_id, w.kind,
               w.kind NOT IN ({non_dismissal}), w.kind IN ({credited}), d.bowler_id,
               w.fielder_ids, w.fielder_is_substitute
        FROM raw_wickets w JOIN raw_deliveries d USING (match_id, innings_no, seq_no)
        ORDER BY ALL;
        """
    )


def _load_participation(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        INSERT INTO match_players
        SELECT mp.match_id, tm.team_season_id, mp.player_id, mp.list_position,
               CASE
                   WHEN sub_in.reason = 'impact_player' THEN 'impact_substitute'
                   WHEN sub_in.reason = 'concussion_substitute' THEN 'concussion_substitute'
                   ELSE 'playing_xi'
               END,
               sub_out.player_out_id IS NOT NULL
        FROM raw_match_players mp
        JOIN matches m USING (match_id)
        JOIN team_map tm ON tm.year = year(m.match_date) AND tm.raw_name = mp.team
        LEFT JOIN (
            SELECT DISTINCT match_id, player_in_id, reason
            FROM raw_replacements WHERE kind = 'match'
        ) sub_in ON sub_in.match_id = mp.match_id AND sub_in.player_in_id = mp.player_id
        LEFT JOIN (
            SELECT DISTINCT match_id, player_out_id FROM raw_replacements WHERE kind = 'match'
        ) sub_out ON sub_out.match_id = mp.match_id AND sub_out.player_out_id = mp.player_id
        ORDER BY mp.match_id, tm.team_season_id, mp.list_position;

        INSERT INTO substitutions
        SELECT r.match_id, r.innings_no, r.seq_no,
               row_number() OVER (PARTITION BY r.match_id, r.innings_no, r.seq_no
                                  ORDER BY r.kind, r.player_in_id),
               r.kind, r.reason,
               CASE
                   WHEN r.kind = 'match' THEN tm.team_season_id
                   WHEN r.role = 'bowler' THEN it.bowling_team_id
                   ELSE it.batting_team_id
               END,
               r.player_in_id, r.player_out_id, r.role
        FROM raw_replacements r
        JOIN matches m USING (match_id)
        JOIN innings_teams it USING (match_id, innings_no)
        LEFT JOIN team_map tm ON tm.year = year(m.match_date) AND tm.raw_name = r.team
        ORDER BY ALL;
        """
    )


def _write_meta(con: duckdb.DuckDBPyConnection, inputs: BuildInputs) -> None:
    meta = {
        "data_version": inputs.data_version,
        "pipeline_version": __version__,
        "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "competition_id": COMPETITION_ID,
        "player_attributes": (
            inputs.attributes_csv.name
            if inputs.attributes_csv is not None and inputs.attributes_csv.exists()
            else "none"
        ),
    }
    con.executemany("INSERT INTO meta VALUES (?, ?)", [list(kv) for kv in meta.items()])
