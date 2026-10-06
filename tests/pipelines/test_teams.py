"""Team Analytics tables: results, net run rate credits, home grounds, form and league tables."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.reference import (
    AbandonedFixture,
    LeagueTablesConfig,
    TableRow,
    VoidedMatch,
)
from criciq_pipelines.teams import (
    FORM_MATCHES,
    TEAM_TABLES,
    build_team_tables,
    check_league_tables,
)

CORE = (
    "competitions",
    "matches",
    "seasons",
    "team_seasons",
    "innings",
    "deliveries",
    "wickets",
    "venues",
)


@pytest.fixture(scope="module")
def con(fixture_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_serving_db), read_only=True)
    yield connection
    connection.close()


def _rebuilt(serving: Path, tables: LeagueTablesConfig) -> duckdb.DuckDBPyConnection:
    """The team tables rebuilt in memory from the serving copies of the core tables."""
    mem = duckdb.connect()
    mem.execute(f"ATTACH '{serving.as_posix()}' AS src (READ_ONLY)")
    for table in CORE:
        mem.execute(f"CREATE TABLE {table} AS SELECT * FROM src.{table}")
    mem.execute("DETACH src")
    build_team_tables(mem, tables)
    return mem


def _side(con: duckdb.DuckDBPyConnection, match_id: int, franchise: str) -> dict[str, object]:
    cursor = con.execute(
        "SELECT * FROM team_matches WHERE match_id = ? AND franchise_id = ?", [match_id, franchise]
    )
    columns = [d[0] for d in cursor.description or []]
    row = cursor.fetchone()
    assert row is not None, (match_id, franchise)
    return dict(zip(columns, row, strict=True))


def test_tables_exist(con: duckdb.DuckDBPyConnection) -> None:
    for table in TEAM_TABLES:
        assert con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] > 0  # type: ignore[index]


def test_every_match_has_two_consistent_sides(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT match_id, count(*), list(result ORDER BY result), bool_and(tied) = bool_or(tied)
        FROM team_matches GROUP BY match_id
        """
    ).fetchall()
    assert len(rows) == con.execute("SELECT count(*) FROM matches").fetchone()[0]  # type: ignore[index]
    for match_id, sides, results, tie_agrees in rows:
        assert sides == 2, match_id
        assert results in (["lost", "won"], ["no_result", "no_result"]), (match_id, results)
        assert tie_agrees


def test_net_run_rate_credits(con: duckdb.DuckDBPyConnection) -> None:
    # Bowled out for 82 in 15.1 overs: charged the full 20 overs.
    rcb = _side(con, 335982, "RCB")
    assert (rcb["runs_for"], rcb["balls_for"]) == (82, 91)
    assert (rcb["nrr_runs_for"], rcb["nrr_balls_for"]) == (82, 120)
    assert (rcb["nrr_runs_against"], rcb["nrr_balls_against"]) == (222, 120)
    # 2023 final, a D/L chase of 171 in 15 overs: GT are credited 170 from 15 overs.
    gt = _side(con, 1370353, "GT")
    assert (gt["nrr_runs_for"], gt["nrr_balls_for"]) == (170, 90)
    assert (gt["nrr_runs_against"], gt["nrr_balls_against"]) == (171, 90)
    # A seven-ball over counts as one over bowled: 121 legal balls are 20 overs.
    first = con.execute(
        """
        SELECT t.nrr_balls_for, i.legal_balls FROM team_matches t
        JOIN innings i ON i.match_id = t.match_id AND i.batting_team_id = t.team_id
        WHERE t.match_id = 419155 AND i.innings_no = 1
        """
    ).fetchone()
    assert first == (120, 121)


def test_no_result_is_left_out_of_net_run_rate(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        "SELECT result, nrr_runs_for, nrr_balls_against FROM team_matches WHERE match_id = 1359519"
    ).fetchall()
    assert rows == [("no_result", None, None)] * 2


def test_margins_and_close_finishes(con: duckdb.DuckDBPyConnection) -> None:
    mi = _side(con, 1181768, "MI")
    assert mi["result"] == "won"
    assert mi["win_by_runs"] == 1
    assert mi["is_close"]
    assert _side(con, 1181768, "CSK")["is_close"]
    kkr = _side(con, 335982, "KKR")
    assert kkr["result"] == "won"
    assert not kkr["is_close"]
    ties = con.execute("SELECT count(*) FROM team_matches WHERE tied AND NOT is_close").fetchone()
    assert ties == (0,)


def test_home_and_away_are_mirror_images(con: duckdb.DuckDBPyConnection) -> None:
    pairs = con.execute(
        """
        SELECT a.venue_type, b.venue_type FROM team_matches a
        JOIN team_matches b ON b.match_id = a.match_id AND b.franchise_id = a.opponent_id
        """
    ).fetchall()
    mirror = {"home": "away", "away": "home", "neutral": "neutral"}
    assert all(mirror[a] == b for a, b in pairs)
    # 2009 was played in South Africa: nobody was at home.
    assert con.execute(
        "SELECT DISTINCT venue_type FROM team_matches WHERE season = 2009"
    ).fetchall() == [("neutral",)]


def test_form_counts_only_earlier_matches(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT franchise_id, form_won, form_decided,
               row_number() OVER (PARTITION BY franchise_id ORDER BY match_order) AS n
        FROM team_matches
        """
    ).fetchall()
    for franchise, won, decided, n in rows:
        assert 0 <= won <= decided <= min(n - 1, FORM_MATCHES), franchise
        if n == 1:
            assert decided == 0


def test_phases_add_up_to_innings_totals(con: duckdb.DuckDBPyConnection) -> None:
    mismatched = con.execute(
        """
        SELECT i.match_id, i.innings_no, i.runs, p.runs, i.legal_balls, p.balls
        FROM innings i
        JOIN (
            SELECT match_id, innings_no, sum(runs) AS runs, sum(balls) AS balls
            FROM team_innings_phases GROUP BY ALL
        ) p USING (match_id, innings_no)
        WHERE NOT i.is_super_over AND (i.runs <> p.runs OR i.legal_balls <> p.balls)
        """
    ).fetchall()
    assert mismatched == []


def test_season_records(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT season, franchise_id, won, no_result, abandoned, points, position, finish
        FROM team_season_records
        """
    ).fetchall()
    for _, _, won, no_result, abandoned, points, _, _ in rows:
        assert points == 2 * won + no_result + abandoned
    finishes = {(season, team): finish for season, team, *_, finish in rows}
    assert finishes[(2019, "MI")] == "champion"
    assert finishes[(2019, "CSK")] == "runner_up"
    assert finishes[(2023, "CSK")] == "champion"
    assert finishes[(2016, "SRH")] == "champion"
    positions = con.execute(
        "SELECT season, list(position ORDER BY position) FROM team_season_records GROUP BY season"
    ).fetchall()
    for _, ranks in positions:
        assert ranks == list(range(1, len(ranks) + 1))


def test_abandoned_and_voided_fixtures(fixture_serving_db: Path) -> None:
    tables = LeagueTablesConfig(
        abandoned=[AbandonedFixture(season=2019, teams=("MI", "CSK"))],
        voided=[VoidedMatch(match_id=1359519, note="test")],
    )
    mem = _rebuilt(fixture_serving_db, tables)
    try:
        mi = mem.execute(
            "SELECT abandoned, played, points, won FROM team_season_records "
            "WHERE season = 2019 AND franchise_id = 'MI'"
        ).fetchone()
        assert mi is not None
        abandoned, played, points, won = mi
        assert abandoned == 1
        assert points == 2 * won + 1
        assert played >= 1
        voided = mem.execute(
            "SELECT bool_or(in_table) FROM team_matches WHERE match_id = 1359519"
        ).fetchone()
        assert voided == (False,)
    finally:
        mem.close()


def _official(con: duckdb.DuckDBPyConnection, season: int) -> list[TableRow]:
    return [
        TableRow(franchise_id=f, won=w, lost=lost, no_result=nr, points=pts, nrr=float(nrr or 0.0))
        for f, w, lost, nr, pts, nrr in con.execute(
            """
            SELECT franchise_id, won, lost, no_result + abandoned, points, nrr
            FROM team_season_records WHERE season = ? ORDER BY position
            """,
            [season],
        ).fetchall()
    ]


def test_league_table_check(con: duckdb.DuckDBPyConnection) -> None:
    season = 2008
    official = _official(con, season)
    assert len(official) > 1
    passed = check_league_tables(con, LeagueTablesConfig(seasons={season: official}))
    assert [c.passed for c in passed] == [True]

    swapped = [official[1], official[0], *official[2:]]
    wrong_nrr = [official[0].model_copy(update={"nrr": official[0].nrr + 0.01}), *official[1:]]
    for bad in (swapped, wrong_nrr):
        checks = check_league_tables(con, LeagueTablesConfig(seasons={season: bad}))
        assert [c.passed for c in checks] == [False]

    # A season the data does not fully cover is not checked.
    padded = [official[0].model_copy(update={"won": official[0].won + 5}), *official[1:]]
    assert check_league_tables(con, LeagueTablesConfig(seasons={season: padded})) == []
