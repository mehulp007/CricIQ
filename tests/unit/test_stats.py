"""Shared statistics: the Python and SQL forms agree, and ties share a rank."""

from __future__ import annotations

import duckdb
import pytest

from criciq_core import stats


@pytest.mark.parametrize(
    ("fn", "args", "expected"),
    [
        (stats.batting_average, (450, 9), 50.0),
        (stats.batting_average, (77, 0), None),
        (stats.strike_rate, (75, 42), 178.57),
        (stats.strike_rate, (0, 0), None),
        (stats.economy, (27, 24), 6.75),
        (stats.bowling_average, (300, 12), 25.0),
        (stats.bowling_strike_rate, (240, 9), 26.67),
        (stats.balls_per_wicket, (120, 0), None),
        (stats.percent, (11, 24), 45.8),
        (stats.run_rate, (155, 120), 7.75),
        (stats.per, (161, 2), 80.5),
        (stats.per, (None, 3), None),
    ],
)
def test_definitions(fn, args, expected) -> None:  # type: ignore[no-untyped-def]
    assert fn(*args) == expected


@pytest.mark.parametrize(
    ("py", "sql", "args"),
    [
        (stats.batting_average, stats.sql_batting_average("a", "b"), (1234, 37)),
        (stats.strike_rate, stats.sql_strike_rate("a", "b"), (1234, 911)),
        (stats.economy, stats.sql_economy("a", "b"), (1234, 997)),
        (stats.bowling_strike_rate, stats.sql_bowling_strike_rate("a", "b"), (997, 41)),
        (stats.percent, stats.sql_percent("a", "b"), (377, 911)),
        (stats.run_rate, stats.sql_run_rate("a", "b"), (155, 0)),
    ],
)
def test_sql_matches_python(py, sql, args) -> None:  # type: ignore[no-untyped-def]
    with duckdb.connect() as con:
        found = con.execute(
            f"SELECT {sql} FROM (SELECT ?::DOUBLE AS a, ?::DOUBLE AS b)", list(args)
        ).fetchone()
    assert found is not None
    assert found[0] == py(*args)


def test_ranks_share_ties_and_skip() -> None:
    values = [10, 8, 8, 5, None, None]
    assert stats.ranks(values, lambda v: v) == [
        (1, False),
        (2, True),
        (2, True),
        (4, False),
        (5, False),
        (6, False),
    ]


def test_ranks_of_nothing() -> None:
    assert stats.ranks([], lambda v: v) == []
