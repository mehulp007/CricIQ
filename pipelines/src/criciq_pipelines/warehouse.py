"""Build the normalized DuckDB warehouse from interim Parquet + reference config.

The warehouse holds every competition in ``config/competitions.yaml`` (or the
selected ones). Each match is assigned to a competition from its own details
(event name, match type, gender), so it does not matter which archive it came
from; matches that belong to no competition are left out.

The build is all-or-nothing: it writes to a temporary file and only replaces
the live warehouse once every table has loaded under the schema's key,
reference and domain constraints. Curated (``strict``) competitions fail on an
unknown team or venue; the others add new teams and venues automatically and
list them in ``auto_added`` for review.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from criciq_pipelines import __version__
from criciq_pipelines.reference import (
    Competition,
    CompetitionsConfig,
    TeamsConfig,
    VenueCountriesConfig,
    VenuesConfig,
    load_competitions,
    load_teams,
    load_venue_countries,
    load_venues,
)

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
# A national side counts as active if it played in the competition's last few seasons.
ACTIVE_WINDOW = 3


class WarehouseBuildError(RuntimeError):
    """Raised when inputs cannot be mapped onto the warehouse model.

    ``match_ids`` names the matches at fault where they are known (an unknown team
    or ground in a curated competition), so a data sync can set them aside.
    """

    def __init__(self, message: str, match_ids: Iterable[int] = ()) -> None:
        super().__init__(message)
        self.match_ids = frozenset(match_ids)


def _insert_many(con: duckdb.DuckDBPyConnection, sql: str, rows: list[Any]) -> None:
    if rows:
        con.executemany(sql, rows)


@dataclass(frozen=True)
class BuildInputs:
    interim_dir: Path
    people_csv: Path
    data_version: str
    attributes_csv: Path | None = None
    config_dir: Path | None = None
    # Competition ids to build; None builds every configured competition.
    competitions: tuple[str, ...] | None = None


def build_warehouse(inputs: BuildInputs, target: Path) -> dict[str, int]:
    """Build the warehouse at ``target`` and return row counts per table."""
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".building")
    staging.unlink(missing_ok=True)

    config = load_competitions(inputs.config_dir)
    competitions = config.select(list(inputs.competitions) if inputs.competitions else None)
    teams = {c.teams: load_teams(c.teams, inputs.config_dir) for c in competitions}
    venues = load_venues(inputs.config_dir)
    places = load_venue_countries(inputs.config_dir)

    con = duckdb.connect(str(staging))
    try:
        con.execute(resources.files("criciq_pipelines").joinpath("sql/schema.sql").read_text())
        _register_interim(con, inputs.interim_dir)
        _classify(con, config, competitions)
        _quarantine(con, competitions, inputs.people_csv)
        _load_competitions(con, competitions)
        _load_seasons(con, competitions)
        _load_teams(con, competitions, teams)
        _load_venues(con, competitions, venues, places)
        _load_players(con, inputs.people_csv, inputs.attributes_csv)
        _load_matches(con)
        _load_innings_and_deliveries(con)
        _load_participation(con)
        _write_meta(con, inputs, competitions)
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
    "teams",
    "competition_teams",
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
    "auto_added",
    "quarantine",
)

_INTERIM = (
    "matches",
    "innings",
    "deliveries",
    "wickets",
    "replacements",
    "match_players",
    "registry",
)


def _register_interim(con: duckdb.DuckDBPyConnection, interim_dir: Path) -> None:
    for name in _INTERIM:
        path = (interim_dir / f"{name}.parquet").as_posix()
        con.execute(f"CREATE TEMP VIEW all_{name} AS SELECT * FROM read_parquet('{path}')")


def _classify(
    con: duckdb.DuckDBPyConnection, config: CompetitionsConfig, selected: list[Competition]
) -> None:
    """Assign every match to its competition and expose only selected ones as raw_*."""
    rows = con.execute(
        "SELECT match_id, event_name, gender, match_type, team_type FROM all_matches"
    ).fetchall()
    chosen = {c.id for c in selected}
    assigned = []
    for match_id, event_name, gender, match_type, team_type in rows:
        competition = config.classify(
            {
                "event_name": event_name,
                "gender": gender,
                "match_type": match_type,
                "team_type": team_type,
            }
        )
        if competition is not None and competition.id in chosen:
            assigned.append((match_id, competition.id))
    con.execute("CREATE TEMP TABLE match_competition (match_id BIGINT, competition_id VARCHAR)")
    if assigned:
        con.executemany("INSERT INTO match_competition VALUES (?, ?)", assigned)
    for name in _INTERIM:
        con.execute(
            f"""
            CREATE TEMP VIEW raw_{name} AS
            SELECT * FROM all_{name} WHERE match_id IN (SELECT match_id FROM match_competition)
            """
        )


# Source errors that would break the warehouse's keys or references, each a query
# returning (match_id, detail). A match with one is set aside, not loaded.
_QUARANTINE_RULES = {
    "player_on_both_sides": """
        SELECT match_id, 'player ' || player_id || ' is listed for both sides'
        FROM raw_match_players GROUP BY match_id, player_id HAVING count(*) > 1
    """,
    "player_missing_from_register": """
        SELECT DISTINCT match_id, 'player ' || person_id || ' is not in people.csv'
        FROM raw_registry WHERE person_id NOT IN (SELECT identifier FROM people_ids)
    """,
}


def _quarantine(
    con: duckdb.DuckDBPyConnection, competitions: list[Competition], people_csv: Path
) -> None:
    """Set aside matches with source errors (``quarantine`` table).

    In a strict (curated) competition any such match fails the build instead.
    """
    con.execute(
        f"""
        CREATE TEMP TABLE people_ids AS
        SELECT identifier FROM read_csv('{people_csv.as_posix()}', all_varchar = true,
                                        header = true)
        """
    )
    con.execute(
        """
        CREATE TABLE quarantine (
            match_id BIGINT NOT NULL, competition_id VARCHAR NOT NULL,
            rule VARCHAR NOT NULL, detail VARCHAR NOT NULL
        )
        """
    )
    for rule, sql in _QUARANTINE_RULES.items():
        con.execute(
            f"""
            INSERT INTO quarantine
            SELECT q.match_id, mc.competition_id, '{rule}', q.detail
            FROM ({sql}) q (match_id, detail) JOIN match_competition mc USING (match_id)
            """
        )
    strict = [c.id for c in competitions if c.strict]
    failures = con.execute(
        "SELECT match_id, competition_id, detail FROM quarantine "
        "WHERE list_contains(?, competition_id)",
        [strict or [""]],
    ).fetchall()
    if failures:
        raise WarehouseBuildError(
            f"source errors in curated competitions: {failures[:5]}", (f[0] for f in failures)
        )
    con.execute("DELETE FROM match_competition WHERE match_id IN (SELECT match_id FROM quarantine)")


# --------------------------------------------------------------------------- reference


def _load_competitions(con: duckdb.DuckDBPyConnection, competitions: list[Competition]) -> None:
    _insert_many(
        con,
        "INSERT INTO competitions VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            [c.id, c.name, c.short_name, c.format, c.gender, c.team_type, c.switcher]
            for c in competitions
        ],
    )


def _load_seasons(con: duckdb.DuckDBPyConnection, competitions: list[Competition]) -> None:
    """A season per competition and year; ``match_season`` maps every match to one.

    Label-based seasons ("2023/24") take the year of their last match, and labels
    ending in the same year are one season (PSL 2021 was interrupted and finished
    under a second label); calendar seasons are the year of a match's first day.
    """
    con.execute(
        """
        CREATE TEMP TABLE match_season (
            match_id BIGINT, competition_id VARCHAR, year INTEGER, season_id VARCHAR
        )
        """
    )
    for c in competitions:
        if c.season_basis == "label":
            con.execute(
                """
                CREATE OR REPLACE TEMP TABLE label_years AS
                SELECT m.season_label, max(year(m.match_date)) AS year
                FROM raw_matches m JOIN match_competition mc USING (match_id)
                WHERE mc.competition_id = ?
                GROUP BY m.season_label
                """,
                [c.id],
            )
            year_sql = "ly.year"
            join_sql = "JOIN label_years ly ON ly.season_label = m.season_label"
        else:
            year_sql = "year(m.match_date)"
            join_sql = ""
        con.execute(
            f"""
            INSERT INTO match_season
            SELECT m.match_id, mc.competition_id, {year_sql}, mc.competition_id || '-' || {year_sql}
            FROM raw_matches m JOIN match_competition mc USING (match_id) {join_sql}
            WHERE mc.competition_id = ?
            """,
            [c.id],
        )
        label_sql = "min(m.season_label)" if c.season_basis == "label" else "ms.year::VARCHAR"
        con.execute(
            f"""
            INSERT INTO seasons
            SELECT ms.season_id, ms.competition_id, ms.year, {label_sql},
                   coalesce(ms.year >= ?, false), min(m.match_date), max(m.end_date)
            FROM match_season ms JOIN raw_matches m USING (match_id)
            WHERE ms.competition_id = ?
            GROUP BY ms.season_id, ms.competition_id, ms.year
            ORDER BY ms.year
            """,
            [c.rules.impact_player_from, c.id],
        )


def _slug_id(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "", ascii_name.upper())[:12] or "TEAM"


def _load_teams(
    con: duckdb.DuckDBPyConnection,
    competitions: list[Competition],
    configs: dict[str, TeamsConfig],
) -> None:
    """Resolve every (competition, season, raw team name) to a team and team-season.

    Club team-seasons keep the v1 id (``MI-2019``); national sides play in several
    competitions, so theirs carry the competition (``ODI-IND-2019``).
    """
    team_rows: dict[str, list[object]] = {}
    for config in configs.values():
        for t in config.teams:
            if t.id in team_rows:
                raise WarehouseBuildError(f"team id {t.id!r} is used by more than one team")
            team_type = "national" if config.name == "national" else "club"
            colors = t.colors
            team_rows[t.id] = [
                t.id,
                t.name,
                team_type,
                colors.primary if colors else None,
                colors.secondary if colors else None,
                True,
            ]

    by_id = {t.id: t for config in configs.values() for t in config.teams}
    team_season_rows = []
    competition_team_rows = []
    auto: list[tuple[str, str, str, str]] = []
    for c in competitions:
        config = configs[c.teams]
        pairs = con.execute(
            """
            SELECT DISTINCT ms.year, t.team
            FROM match_season ms
            JOIN (SELECT match_id, team1 AS team FROM raw_matches
                  UNION SELECT match_id, team2 FROM raw_matches) t USING (match_id)
            WHERE ms.competition_id = ?
            ORDER BY 1, 2
            """,
            [c.id],
        ).fetchall()
        seen: dict[str, list[int]] = {}
        for year, raw_name in pairs:
            try:
                team_id = config.resolve(raw_name, year).id
            except LookupError as exc:
                if c.strict:
                    culprits = con.execute(
                        """
                        SELECT match_id FROM match_season JOIN raw_matches USING (match_id)
                        WHERE competition_id = ? AND year = ? AND ? IN (team1, team2)
                        """,
                        [c.id, year, raw_name],
                    ).fetchall()
                    raise WarehouseBuildError(str(exc), (m for (m,) in culprits)) from None
                team_id = _slug_id(raw_name)
                if team_id not in team_rows:
                    team_type = "national" if c.team_type == "national" else "club"
                    team_rows[team_id] = [team_id, raw_name, team_type, None, None, False]
                    auto.append(("team", c.id, team_id, raw_name))
            seen.setdefault(team_id, []).append(year)
            prefix = "" if c.team_type == "club" else f"{c.id}-"
            team_season_rows.append(
                [f"{prefix}{team_id}-{year}", team_id, f"{c.id}-{year}", raw_name]
            )
        latest = max((y for ys in seen.values() for y in ys), default=0)
        if c.team_type == "club":
            # Every curated club of the competition, as listed (v1: franchises).
            for t in config.teams:
                competition_team_rows.append(
                    [c.id, t.id, t.first_season, t.last_season, t.last_season is None]
                )
            for team_id, years in seen.items():
                if team_id not in by_id:
                    competition_team_rows.append([c.id, team_id, min(years), None, True])
        else:
            for team_id, years in seen.items():
                active = max(years) > latest - ACTIVE_WINDOW
                competition_team_rows.append(
                    [c.id, team_id, min(years), None if active else max(years), active]
                )

    _insert_many(con, "INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?)", list(team_rows.values()))
    _insert_many(con, "INSERT INTO competition_teams VALUES (?, ?, ?, ?, ?)", competition_team_rows)
    _insert_many(con, "INSERT INTO team_seasons VALUES (?, ?, ?, ?)", team_season_rows)
    con.execute(
        """
        CREATE TEMP TABLE team_map AS
        SELECT s.competition_id, s.year, t.display_name AS raw_name, t.team_season_id
        FROM team_seasons t JOIN seasons s USING (season_id)
        """
    )
    con.execute(
        """
        CREATE TABLE auto_added (
            kind VARCHAR NOT NULL, competition_id VARCHAR NOT NULL,
            id VARCHAR NOT NULL, raw_name VARCHAR NOT NULL, detail VARCHAR
        )
        """
    )
    if auto:
        _insert_many(
            con, "INSERT INTO auto_added VALUES (?, ?, ?, ?, NULL)", [list(a) for a in auto]
        )


def _venue_base(raw_name: str) -> str:
    return raw_name.split(",")[0].strip()


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _load_venues(
    con: duckdb.DuckDBPyConnection,
    competitions: list[Competition],
    venues: VenuesConfig,
    places: VenueCountriesConfig,
) -> None:
    """Curated venues, plus grounds added automatically for non-strict competitions.

    A match's ground is found from its venue name and city: a few names belong to
    several grounds ("National Stadium" is in Karachi and in Bermuda), so those are
    told apart by city (`shared` in venue_countries.yaml). The result is the temp
    table ``venue_map`` (venue name, city -> venue id) that the matches load joins."""
    _insert_many(
        con,
        "INSERT INTO venues VALUES (?, ?, ?, ?, ?, true)",
        [[v.id, v.name, v.city, v.country, v.notes] for v in venues.venues],
    )
    curated_aliases = venues.alias_map()
    curated_ids = {v.id for v in venues.venues}
    curated_base = {_venue_base(a): vid for a, vid in curated_aliases.items()}
    strict = [c.id for c in competitions if c.strict]
    rows = con.execute(
        """
        SELECT m.venue_raw, m.city_raw, count(*), bool_or(list_contains(?, mc.competition_id)),
               min(mc.competition_id)
        FROM raw_matches m JOIN match_competition mc USING (match_id)
        GROUP BY m.venue_raw, m.city_raw ORDER BY 1, 2 NULLS LAST
        """,
        [strict or [""]],
    ).fetchall()
    unmapped_strict = sorted(
        {raw for raw, _, _, is_strict, _ in rows if is_strict and raw not in curated_aliases}
    )
    if unmapped_strict:
        names = ", ".join(repr(u) for u in unmapped_strict)
        culprits = con.execute(
            """
            SELECT m.match_id FROM raw_matches m JOIN match_competition mc USING (match_id)
            WHERE list_contains(?, m.venue_raw) AND list_contains(?, mc.competition_id)
            """,
            [unmapped_strict, strict],
        ).fetchall()
        raise WarehouseBuildError(
            f"unmapped venues (add to config/venues.yaml): {names}", (m for (m,) in culprits)
        )

    # A name that only ever means one ground takes the city most of its matches give.
    usual_city: dict[str, str | None] = {}
    for raw, city_raw, _, _, _ in sorted(
        rows, key=lambda r: (r[0], r[1] is None, -r[2], r[1] or "")
    ):
        usual_city.setdefault(raw, city_raw)

    new_venues: dict[str, list[object]] = {}
    auto_rows: list[list[object]] = []
    resolved: dict[str, str] = {}
    venue_map: list[tuple[str, str | None, str]] = []
    for raw, city_raw, _, _, competition_id in rows:
        base = _venue_base(raw)
        suffix = raw.split(",", 1)[1].split(",")[0].strip() if "," in raw else None
        if base in places.shared:
            city = city_raw or suffix
            ground = places.shared[base].get(city or "")
            if ground is None:
                raise WarehouseBuildError(
                    f"venue {raw!r} in {city!r}: several grounds share this name; add the city "
                    "under `shared` in config/venue_countries.yaml"
                )
            venue_id, name = ground.id, ground.name or base
            country = ground.country or places.cities.get(city or "")
        elif raw in resolved:
            venue_map.append((raw, city_raw, resolved[raw]))
            continue
        elif raw in curated_aliases or places.merges.get(base, base) in curated_base:
            venue_id = curated_aliases.get(raw) or curated_base[places.merges.get(base, base)]
            resolved[raw] = venue_id
            venue_map.append((raw, city_raw, venue_id))
            continue
        else:
            name = places.merges.get(base, base)
            place = places.venues.get(name) or places.venues.get(base)
            city = place.city if place else (usual_city[raw] or suffix)
            country = place.country if place else places.cities.get(city or "")
            venue_id = _slug(name)
            clashes = venue_id in curated_ids or (
                venue_id in new_venues and new_venues[venue_id][3] != country
            )
            if clashes:
                venue_id = f"{venue_id}-{_slug(country or 'unknown')}"
            resolved[raw] = venue_id
        if venue_id not in new_venues and venue_id not in curated_ids:
            new_venues[venue_id] = [venue_id, name, city, country, None]
            auto_rows.append(
                ["venue", competition_id, venue_id, raw, None if country else "no country"]
            )
        venue_map.append((raw, city_raw, venue_id))

    _insert_many(con, "INSERT INTO venues VALUES (?, ?, ?, ?, ?, false)", list(new_venues.values()))
    # Every curated name, used or not, plus every name a match used.
    aliases = sorted(
        set(curated_aliases.items()) | {(raw, venue_id) for raw, _, venue_id in venue_map}
    )
    _insert_many(
        con,
        "INSERT INTO venue_aliases VALUES (?, ?, ?)",
        [[raw, vid, curated_aliases.get(raw) == vid] for raw, vid in aliases],
    )
    con.execute(
        "CREATE TEMP TABLE venue_map (raw_name VARCHAR, city_raw VARCHAR, venue_id VARCHAR)"
    )
    _insert_many(con, "INSERT INTO venue_map VALUES (?, ?, ?)", [list(r) for r in venue_map])
    if auto_rows:
        _insert_many(con, "INSERT INTO auto_added VALUES (?, ?, ?, ?, ?)", auto_rows)


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
        """
        CREATE TEMP TABLE match_team AS
        SELECT m.match_id, ms.competition_id, ms.year, ms.season_id
        FROM raw_matches m JOIN match_season ms USING (match_id);

        INSERT INTO matches
        SELECT
            m.match_id,
            mt.competition_id,
            mt.season_id,
            row_number() OVER (
                PARTITION BY mt.competition_id
                ORDER BY m.match_date, m.match_number NULLS LAST, m.match_id
            ),
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
                WHEN m.outcome_result = 'draw' THEN 'draw'
                WHEN m.outcome_result = 'no result' THEN 'no_result'
                WHEN m.outcome_winner IS NOT NULL THEN 'win'
            END,
            coalesce(w.team_season_id, el.team_season_id, bo.team_season_id),
            m.outcome_by_runs,
            m.outcome_by_wickets,
            m.outcome_by_innings,
            m.outcome_method,
            m.outcome_eliminator IS NOT NULL,
            m.outcome_bowl_out IS NOT NULL,
            m.scheduled_overs,
            m.balls_per_over,
            (m.end_date - m.match_date) + 1,
            m.player_of_match_ids,
            m.cricsheet_version,
            m.event_name,
            m.match_type_number,
            coalesce(m.has_supersubs, false)
        FROM raw_matches m
        JOIN match_team mt USING (match_id)
        JOIN venue_map va ON va.raw_name = m.venue_raw
             AND va.city_raw IS NOT DISTINCT FROM m.city_raw
        JOIN team_map t1 ON t1.competition_id = mt.competition_id AND t1.year = mt.year
             AND t1.raw_name = m.team1
        JOIN team_map t2 ON t2.competition_id = mt.competition_id AND t2.year = mt.year
             AND t2.raw_name = m.team2
        LEFT JOIN team_map tw ON tw.competition_id = mt.competition_id AND tw.year = mt.year
             AND tw.raw_name = m.toss_winner
        LEFT JOIN team_map w ON w.competition_id = mt.competition_id AND w.year = mt.year
             AND w.raw_name = m.outcome_winner
        LEFT JOIN team_map el ON el.competition_id = mt.competition_id AND el.year = mt.year
             AND el.raw_name = m.outcome_eliminator
        LEFT JOIN team_map bo ON bo.competition_id = mt.competition_id AND bo.year = mt.year
             AND bo.raw_name = m.outcome_bowl_out
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
        JOIN match_team mt USING (match_id)
        JOIN team_map bat ON bat.competition_id = mt.competition_id AND bat.year = mt.year
             AND bat.raw_name = i.team;

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
               coalesce(agg.runs, 0)
                   + coalesce(i.penalty_runs_pre, 0) + coalesce(i.penalty_runs_post, 0),
               coalesce(agg.wickets, 0), coalesce(agg.legal_balls, 0),
               coalesce(agg.extras, 0), i.absent_hurt_ids, i.miscounted_overs_json,
               coalesce(i.declared, false), coalesce(i.forfeited, false),
               NOT i.is_super_over AND i.innings_no > 1
                   AND t.batting_team_id = lag(t.batting_team_id) OVER (
                       PARTITION BY i.match_id ORDER BY i.innings_no),
               coalesce(i.penalty_runs_pre, 0) + coalesce(i.penalty_runs_post, 0)
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
        JOIN match_team mt USING (match_id)
        JOIN team_map tm ON tm.competition_id = mt.competition_id AND tm.year = mt.year
             AND tm.raw_name = mp.team
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
        JOIN match_team mt USING (match_id)
        JOIN innings_teams it USING (match_id, innings_no)
        LEFT JOIN team_map tm ON tm.competition_id = mt.competition_id AND tm.year = mt.year
             AND tm.raw_name = r.team
        ORDER BY ALL;
        """
    )


def _write_meta(
    con: duckdb.DuckDBPyConnection, inputs: BuildInputs, competitions: list[Competition]
) -> None:
    meta = {
        "data_version": inputs.data_version,
        "pipeline_version": __version__,
        "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "competitions": ",".join(c.id for c in competitions),
        "player_attributes": (
            inputs.attributes_csv.name
            if inputs.attributes_csv is not None and inputs.attributes_csv.exists()
            else "none"
        ),
    }
    _insert_many(con, "INSERT INTO meta VALUES (?, ?)", [list(kv) for kv in meta.items()])
