"""The players database: Player Lab tables for every T20 competition and all T20."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_core.phases import default_phase_config
from criciq_pipelines.export import NEUTRAL_COLOR
from criciq_pipelines.player_db import (
    ALL_T20,
    PlayerDatabaseError,
    export_players,
)
from criciq_pipelines.players import PLAYER_TABLES

T20_COMPETITIONS = ["IPL", "BBL", "PSL", "CPL", "SA20", "T20I"]
COMPETITIONS = [*T20_COMPETITIONS, "ODI"]


@pytest.fixture(scope="module")
def con(fixture_players_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_players_db), read_only=True)
    yield connection
    connection.close()


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[object] | None = None) -> list:  # type: ignore[type-arg]
    return con.execute(sql, params or []).fetchall()


def test_a_scope_per_competition_and_one_for_all_t20(con: duckdb.DuckDBPyConnection) -> None:
    scopes = _rows(
        con,
        "SELECT scope_id, schema_name, competition_ids, format FROM scopes ORDER BY display_order",
    )
    # The T20 competitions, all T20 together, then ODIs.
    assert [s[0] for s in scopes] == [*T20_COMPETITIONS, ALL_T20, "ODI"]
    assert {s[0]: s[1] for s in scopes}["SA20"] == "sa20"
    assert {s[0]: s[2] for s in scopes}[ALL_T20] == T20_COMPETITIONS
    assert {s[0]: s[3] for s in scopes}["ODI"] == "ODI"
    # Test cricket comes later.
    assert _rows(con, "SELECT DISTINCT competition_id FROM matches ORDER BY ALL") == sorted(
        (c,) for c in COMPETITIONS
    )


def _content(con: duckdb.DuckDBPyConnection, relation: str, columns: list[tuple[str, str]]) -> set:  # type: ignore[type-arg]
    values = ", ".join(
        f'round("{name}", 9)' if kind == "DOUBLE" else f'"{name}"' for name, kind in columns
    )
    return set(_rows(con, f"SELECT {values} FROM {relation}"))


def test_the_ipl_scope_equals_the_serving_database(
    con: duckdb.DuckDBPyConnection, fixture_serving_db: Path
) -> None:
    con.execute(f"ATTACH '{fixture_serving_db.as_posix()}' AS serving (READ_ONLY)")
    try:
        for table in PLAYER_TABLES:
            columns = [(r[0], r[1]) for r in _rows(con, f"DESCRIBE serving.{table}")]
            expected = _content(con, f"serving.{table}", columns)
            assert expected, table
            assert _content(con, f"ipl.{table}", columns) == expected, table
            count = f"SELECT count(*) FROM {{}}.{table}"
            assert _rows(con, count.format("ipl")) == _rows(con, count.format("serving"))
    finally:
        con.execute("DETACH serving")


def test_par_is_each_competitions_own_rate(
    con: duckdb.DuckDBPyConnection, fixture_full_warehouse: Path
) -> None:
    """League rates come from the competition's own balls, season and phase."""
    phase = default_phase_config().sql_case("d.over_no", "c.format")
    con.execute(f"ATTACH '{fixture_full_warehouse.as_posix()}' AS w (READ_ONLY)")
    try:
        recount = _rows(
            con,
            f"""
            SELECT m.competition_id, s.year, {phase} AS phase,
                   round(sum(d.runs_batter) FILTER (WHERE d.extras_wides = 0)
                         / count(*) FILTER (WHERE d.extras_wides = 0), 9)
            FROM w.deliveries d
            JOIN w.innings i USING (match_id, innings_no)
            JOIN w.matches m USING (match_id)
            JOIN w.seasons s USING (season_id)
            JOIN w.competitions c ON c.competition_id = m.competition_id
            WHERE NOT i.is_super_over AND c.format IN ('T20', 'ODI')
            GROUP BY ALL ORDER BY ALL
            """,
        )
    finally:
        con.execute("DETACH w")
    stored = _rows(
        con,
        """
        SELECT competition_id, season, phase, round(bat_runs_rate, 9)
        FROM league_phase_rates ORDER BY ALL
        """,
    )
    assert stored == recount
    # The same season and phase differ between competitions: each has its own par.
    by_cell: dict[tuple[int, str], set[float]] = {}
    for _, season, phase_key, rate in stored:
        by_cell.setdefault((season, phase_key), set()).add(rate)
    assert any(len(rates) > 1 for rates in by_cell.values())


def test_par_adds_up_across_tables_and_scopes(con: duckdb.DuckDBPyConnection) -> None:
    total = "SELECT round(sum(par_runs), 6) FROM {}.player_batting_{}"
    for scope in ["ipl", "bbl", "t20i", "t20"]:
        assert _rows(con, total.format(scope, "innings")) == _rows(
            con, total.format(scope, "cells")
        )
    parts = sum(_rows(con, total.format(c.lower(), "innings"))[0][0] for c in T20_COMPETITIONS)
    assert _rows(con, total.format("t20", "innings"))[0][0] == pytest.approx(parts)


def test_all_t20_puts_a_career_together(con: duckdb.DuckDBPyConnection) -> None:
    players = _rows(
        con,
        """
        SELECT player_id, sum(matches), min(first_season), max(last_season), count(*)
        FROM player_index WHERE scope_id IN (SELECT unnest(competition_ids) FROM scopes
                                             WHERE scope_id = 'T20')
        GROUP BY player_id HAVING count(*) > 1
        """,
    )
    assert players, "a fixture player who played in two competitions"
    for player_id, matches, first, last, _ in players:
        assert _rows(
            con,
            "SELECT matches, first_season, last_season FROM t20.player_index WHERE player_id = ?",
            [player_id],
        ) == [(matches, first, last)]
    everyone = _rows(
        con, "SELECT count(DISTINCT player_id) FROM player_index WHERE scope_id <> 'ODI'"
    )
    assert _rows(con, "SELECT count(*) FROM t20.player_index") == everyone


def test_all_t20_lists_innings_in_the_order_they_were_played(
    con: duckdb.DuckDBPyConnection,
) -> None:
    assert _rows(
        con,
        """
        SELECT count(*) FROM t20.player_batting_innings b
        JOIN main.matches m USING (match_id) WHERE b.match_order <> m.global_order
        """,
    ) == [(0,)]
    assert _rows(
        con,
        """
        SELECT count(*) FROM bbl.player_batting_innings b
        JOIN main.matches m USING (match_id) WHERE b.match_order <> m.match_order
        """,
    ) == [(0,)]


def test_season_labels(con: duckdb.DuckDBPyConnection) -> None:
    labels = dict(
        ((c, y), label)
        for c, y, label in _rows(con, "SELECT competition_id, year, label FROM seasons")
    )
    assert labels[("BBL", 2024)] == "2023/24"  # a season spanning the new year
    assert labels[("PSL", 2021)] == "2021"
    assert labels[("IPL", 2008)] == "2008"  # Cricsheet calls it "2007/08"


def test_every_team_has_a_colour(con: duckdb.DuckDBPyConnection) -> None:
    assert _rows(con, "SELECT count(*) FROM franchises WHERE primary_color IS NULL") == [(0,)]
    neutral = _rows(
        con, "SELECT count(*) FROM t20i.franchises WHERE primary_color = ?", [NEUTRAL_COLOR]
    )
    assert neutral[0][0] > 0  # associate nations without curated colours


def test_unknown_attributes_get_their_own_cells(con: duckdb.DuckDBPyConnection) -> None:
    """Players whose batting hand or bowling type is unknown still count, as 'unknown'."""
    for sql in (
        "SELECT count(*) > 0 FROM t20.player_batting_cells WHERE bowling_type = 'unknown'",
        "SELECT count(*) > 0 FROM t20.player_bowling_cells WHERE batting_hand = 'unknown'",
    ):
        assert _rows(con, sql) == [(True,)]


def test_a_selection_builds_only_those_competitions(
    fixture_full_warehouse: Path, tmp_path: Path
) -> None:
    target = tmp_path / "players.duckdb"
    export_players(fixture_full_warehouse, target, ["ipl"])
    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert connection.execute(
            "SELECT scope_id, competition_ids FROM scopes ORDER BY display_order"
        ).fetchall() == [("IPL", ["IPL"]), (ALL_T20, ["IPL"])]
    finally:
        connection.close()
    # ODIs alone: no All T20 scope.
    export_players(fixture_full_warehouse, tmp_path / "players-odi.duckdb", ["ODI"])
    connection = duckdb.connect(str(tmp_path / "players-odi.duckdb"), read_only=True)
    try:
        assert connection.execute(
            "SELECT scope_id, competition_ids FROM scopes ORDER BY display_order"
        ).fetchall() == [("ODI", ["ODI"])]
    finally:
        connection.close()
    with pytest.raises(PlayerDatabaseError):
        export_players(fixture_full_warehouse, tmp_path / "none.duckdb", ["TEST"])
    assert not (tmp_path / "none.duckdb").exists()
