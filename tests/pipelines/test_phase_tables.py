"""The Phases page's tables add up to the innings, team and player tables they summarise."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_core.phases import default_phase_config
from criciq_pipelines.phase_tables import PHASE_TABLES


@pytest.fixture(scope="module")
def con(fixture_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_serving_db), read_only=True)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def test_con(fixture_scored_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(
        str(fixture_scored_serving_db.with_name("serving-test.duckdb")), read_only=True
    )
    yield connection
    connection.close()


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[object, ...]]:
    return con.execute(sql).fetchall()


def test_the_export_builds_every_table(con: duckdb.DuckDBPyConnection) -> None:
    for table in PHASE_TABLES:
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        assert count is not None
        assert count[0] > 0, table


def test_overs_add_up_to_the_phases(con: duckdb.DuckDBPyConnection) -> None:
    differences = _rows(
        con,
        """
        SELECT o.match_id, o.innings_no, o.phase
        FROM (SELECT match_id, innings_no, phase, sum(runs) AS runs, sum(balls) AS balls,
                     sum(wickets) AS wickets
              FROM team_innings_overs GROUP BY ALL) o
        FULL JOIN team_innings_phases p USING (match_id, innings_no, phase)
        WHERE o.runs IS DISTINCT FROM p.runs OR o.balls IS DISTINCT FROM p.balls
           OR o.wickets IS DISTINCT FROM p.wickets
        """,
    )
    assert differences == []


def test_overs_are_one_indexed_and_phased_by_config(con: duckdb.DuckDBPyConnection) -> None:
    t20 = default_phase_config().for_format("T20")
    for over, phase in _rows(con, "SELECT DISTINCT over, phase FROM team_innings_overs"):
        assert isinstance(over, int)
        assert over >= 1
        assert t20.phase_for_over_index(over - 1).key == phase


def test_batting_matches_the_player_innings(con: duckdb.DuckDBPyConnection) -> None:
    differences = _rows(
        con,
        """
        SELECT b.player_id, b.match_id, b.innings_no
        FROM (SELECT player_id, match_id, innings_no, sum(balls) AS balls, sum(runs) AS runs,
                     sum(fours) AS fours, sum(sixes) AS sixes, sum(dots) AS dots,
                     sum(outs) AS outs
              FROM phase_batting GROUP BY ALL) b
        JOIN player_batting_innings p USING (player_id, match_id, innings_no)
        WHERE b.balls <> p.balls OR b.runs <> p.runs OR b.fours <> p.fours
           OR b.sixes <> p.sixes OR b.dots <> p.dots OR b.outs <> p.is_out::INTEGER
        """,
    )
    assert differences == []


def test_bowling_matches_the_player_innings(con: duckdb.DuckDBPyConnection) -> None:
    differences = _rows(
        con,
        """
        SELECT b.player_id, b.match_id, b.innings_no
        FROM (SELECT player_id, match_id, innings_no, sum(balls) AS balls, sum(runs) AS runs,
                     sum(wickets) AS wickets, sum(dots) AS dots
              FROM phase_bowling GROUP BY ALL) b
        FULL JOIN player_bowling_innings p USING (player_id, match_id, innings_no)
        WHERE b.balls IS DISTINCT FROM p.balls OR b.runs IS DISTINCT FROM p.runs
           OR b.wickets IS DISTINCT FROM p.wickets OR b.dots IS DISTINCT FROM p.dots
        """,
    )
    assert differences == []


def test_players_carry_their_own_team(con: duckdb.DuckDBPyConnection) -> None:
    wrong = _rows(
        con,
        """
        SELECT b.player_id, b.match_id
        FROM phase_batting b
        JOIN player_batting_innings p USING (player_id, match_id, innings_no)
        WHERE b.team_id <> p.team_id OR b.opposition_id <> p.opposition_id
           OR b.venue_id <> p.venue_id OR b.season <> p.season
        """,
    )
    assert wrong == []


def test_tests_use_their_own_phases(test_con: duckdb.DuckDBPyConnection) -> None:
    phases = {r[0] for r in _rows(test_con, "SELECT DISTINCT phase FROM team_innings_overs")}
    assert phases
    assert phases <= {"new_ball", "middle", "second_new_ball"}
    late = _rows(test_con, "SELECT DISTINCT phase FROM team_innings_overs WHERE over > 80")
    assert late in ([], [("second_new_ball",)])
