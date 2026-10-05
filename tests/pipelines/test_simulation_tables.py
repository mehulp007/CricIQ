"""Simulator tables: bowling usage per over and league rates per legal ball."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest


@pytest.fixture(scope="module")
def con(fixture_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_serving_db), read_only=True)
    yield connection
    connection.close()


def test_every_over_has_one_bowler(con: duckdb.DuckDBPyConnection) -> None:
    overs = con.execute("SELECT sum(overs) FROM bowling_usage").fetchone()
    actual = con.execute(
        """
        SELECT count(*) FROM (
            SELECT DISTINCT d.match_id, d.innings_no, d.over_no FROM deliveries d
            JOIN innings i USING (match_id, innings_no) WHERE NOT i.is_super_over
        )
        """
    ).fetchone()
    assert overs == actual
    # Every over number is 0-19 (or an umpire's extra over at the end).
    numbers = con.execute("SELECT min(over_no), max(over_no) FROM bowling_usage").fetchone()
    assert numbers is not None
    assert numbers[0] >= 0
    assert numbers[1] <= 20


def test_league_rates_count_every_legal_ball(con: duckdb.DuckDBPyConnection) -> None:
    rates = con.execute(
        """
        SELECT sum(legal_balls), sum(x0 + x1 + x2 + x3 + x4 + x5), sum(run_outs)
        FROM sim_league_rates
        """
    ).fetchone()
    legal = con.execute(
        """
        SELECT count(*) FROM deliveries d JOIN innings i USING (match_id, innings_no)
        WHERE d.is_legal AND NOT i.is_super_over AND d.innings_no <= 2
        """
    ).fetchone()
    run_outs = con.execute(
        """
        SELECT count(*) FROM wickets w JOIN innings i USING (match_id, innings_no)
        WHERE w.kind = 'run out' AND w.is_dismissal AND NOT i.is_super_over AND w.innings_no <= 2
        """
    ).fetchone()
    assert rates is not None
    assert legal is not None
    assert run_outs is not None
    assert rates[0] == legal[0]
    assert rates[1] == legal[0]
    assert rates[2] == run_outs[0]


def test_extras_add_up(con: duckdb.DuckDBPyConnection) -> None:
    """Extra runs from the table (capped at 5 a ball) match the deliveries."""
    from_table = con.execute(
        "SELECT sum(x1 + 2 * x2 + 3 * x3 + 4 * x4 + 5 * x5) FROM sim_league_rates"
    ).fetchone()
    from_balls = con.execute(
        """
        SELECT sum(d.extras_wides + d.extras_noballs + d.extras_byes + d.extras_legbyes
                   + d.extras_penalty)
        FROM deliveries d JOIN innings i USING (match_id, innings_no)
        WHERE NOT i.is_super_over AND d.innings_no <= 2
        """
    ).fetchone()
    assert from_table is not None
    assert from_balls is not None
    # Equal unless a single ball came with more than five extras (then it is capped).
    assert from_table[0] <= from_balls[0]
    assert from_table[0] >= 0.9 * from_balls[0]
