"""The Records hub's tables: partnerships, milestones and each match's biggest swing."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_core.records import EVERYONE, default_records_config, load_records_config


@pytest.fixture(scope="module")
def con(fixture_scored_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    yield connection
    connection.close()


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[object, ...]]:
    return con.execute(sql).fetchall()


def test_stands_add_up_to_each_innings(con: duckdb.DuckDBPyConnection) -> None:
    """Every ball belongs to one stand, so the stands make up the innings."""
    wrong = _rows(
        con,
        """
        SELECT p.match_id, p.innings_no
        FROM (SELECT match_id, innings_no, sum(runs) AS runs, sum(balls) AS balls
              FROM partnerships GROUP BY ALL) p
        JOIN (SELECT d.match_id, d.innings_no, sum(d.runs_total) AS runs,
                     count(*) FILTER (WHERE d.is_legal) AS balls
              FROM deliveries d JOIN innings i USING (match_id, innings_no)
              WHERE NOT i.is_super_over GROUP BY ALL) d USING (match_id, innings_no)
        WHERE p.runs <> d.runs OR p.balls <> d.balls
        """,
    )
    assert wrong == []


def test_stands_are_numbered_by_the_wickets_fallen(con: duckdb.DuckDBPyConnection) -> None:
    assert _rows(con, "SELECT * FROM partnerships WHERE wicket NOT BETWEEN 1 AND 11") == []
    # A stand ended by a wicket is followed by one for the next wicket.
    broken = _rows(
        con,
        """
        SELECT p.match_id, p.innings_no, p.wicket FROM partnerships p
        WHERE NOT p.unbroken AND p.wicket < 10 AND NOT EXISTS (
            SELECT 1 FROM partnerships q
            WHERE q.match_id = p.match_id AND q.innings_no = p.innings_no
              AND q.wicket = p.wicket + 1)
          AND p.last_seq < (SELECT max(seq_no) FROM deliveries d
                            WHERE d.match_id = p.match_id AND d.innings_no = p.innings_no)
        """,
    )
    assert broken == []


def test_batters_runs_fit_inside_the_stand(con: duckdb.DuckDBPyConnection) -> None:
    assert _rows(con, "SELECT * FROM partnerships WHERE first_runs + second_runs > runs") == []
    assert _rows(con, "SELECT * FROM partnerships WHERE first_id >= second_id") == []


def test_milestones_match_the_innings(con: duckdb.DuckDBPyConnection) -> None:
    wrong = _rows(
        con,
        """
        SELECT m.player_id, m.match_id FROM batting_milestones m
        JOIN player_batting_innings b USING (player_id, match_id, innings_no)
        WHERE b.runs < 50 OR m.balls_to_50 > b.balls
           OR (b.runs >= 100) <> (m.balls_to_100 IS NOT NULL)
           OR m.balls_to_100 < m.balls_to_50
        """,
    )
    assert wrong == []
    fifties = _rows(con, "SELECT count(*) FROM player_batting_innings WHERE runs >= 50")
    assert _rows(con, "SELECT count(*) FROM batting_milestones") == fifties


def test_swings_are_one_per_match_and_point_the_right_way(
    con: duckdb.DuckDBPyConnection,
) -> None:
    assert (
        _rows(con, "SELECT match_id FROM match_swings GROUP BY match_id HAVING count(*) > 1") == []
    )
    for before, after, swing in _rows(con, "SELECT wp_before, wp_after, swing FROM match_swings"):
        assert isinstance(before, float)
        assert isinstance(after, float)
        assert after > before
        assert after - before == pytest.approx(swing)


def test_the_swing_is_the_largest_in_the_match(con: duckdb.DuckDBPyConnection) -> None:
    larger = _rows(
        con,
        """
        WITH w AS (
            SELECT match_id, abs(wp_team_a - lag(wp_team_a) OVER (
                PARTITION BY match_id, innings_no ORDER BY seq_no)) AS delta
            FROM wp_predictions
        )
        SELECT s.match_id FROM match_swings s JOIN w USING (match_id)
        WHERE w.delta > s.swing + 1e-9
        """,
    )
    assert larger == []


def test_qualifications_by_format() -> None:
    config = default_records_config()
    assert set(config.formats) == {"T20", "ODI", "Test"}
    assert config.qualification("T20", 1000).batting_innings == 20
    assert config.qualification("Test", 1000).innings_balls_bowled is None
    assert config.qualification("T20", 10) == EVERYONE
    assert config.qualification("Test", 10).innings_balls_bowled is None


def test_a_bad_config_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "records.yaml"
    bad.write_text("small_data_matches: 5\nformats:\n  T20:\n    batting_innings: 0\n")
    with pytest.raises(ValueError, match="batting_innings"):
        load_records_config(bad)
