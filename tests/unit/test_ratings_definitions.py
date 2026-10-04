"""The rating components shared by the fit and the API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_core import ratings, style


@pytest.fixture(scope="module")
def con(fixture_scored_serving_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_scored_serving_db), read_only=True)
    yield connection
    connection.close()


def test_components_are_unique_per_role() -> None:
    for role in ("batting", "bowling"):
        keys = [c.key for c in ratings.role_components(role)]
        assert len(keys) == len(set(keys))
        assert ratings.role_balls_key(role) in keys
        assert {"powerplay", "middle", "death", "impact", "consistency"} <= set(keys)


def test_components_needing_scores_are_skipped_without_them() -> None:
    unscored = {"player_batting_innings", "player_batting_phases"}
    assert "impact" not in {c.key for c in ratings.role_components("batting", unscored)}
    assert "impact" in {c.key for c in ratings.role_components("batting")}


def test_window_sums_match_the_source_tables(con: duckdb.DuckDBPyConnection) -> None:
    tables = {name for (name,) in con.execute("SHOW TABLES").fetchall()}
    sums = {
        (component, player): (e, n)
        for component, player, e, n in con.execute(
            ratings.window_sums_sql("batting", tables), [2008, 2100]
        ).fetchall()
    }
    totals = con.execute(
        """
        SELECT player_id, sum(runs - par_runs), sum(balls)
        FROM player_batting_innings GROUP BY player_id
        """
    ).fetchall()
    for player, above, balls in totals:
        e, n = sums[("scoring", player)]
        assert e == pytest.approx(above)
        assert n == balls
    wpa = con.execute("SELECT sum(wpa), count(*) FROM player_wpa WHERE role = 'batting'").fetchone()
    assert wpa is not None
    impact = [v for (c, _), v in sums.items() if c == "impact"]
    assert sum(e for e, _ in impact) == pytest.approx(wpa[0])
    assert sum(n for _, n in impact) == wpa[1]


def test_values_are_oriented_so_higher_is_better() -> None:
    economy = next(c for c in ratings.role_components("bowling") if c.key == "economy")
    assert "par_runs - runs" in economy.sql
    assert economy.value(6.0, 36) == pytest.approx(1.0)  # one run saved per over
    assert economy.value(1.0, 0) is None


@pytest.mark.parametrize("role", ["batting", "bowling"])
def test_style_profiles_have_every_feature(con: duckdb.DuckDBPyConnection, role: str) -> None:
    cursor = con.execute(style.profile_sql(role), style.window_params(2008, 2100))  # type: ignore[arg-type]
    columns = {d[0] for d in cursor.description or []}
    assert {f.key for f in style.features(role)} | {"player_id", "balls"} <= columns  # type: ignore[arg-type]
    rows = cursor.fetchall()
    assert rows
    assert all(row is not None for row in rows)
