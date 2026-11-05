"""Shared analysis helpers: filter clauses and a competition's coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from criciq_api.db import Database
from criciq_api.repositories.common import FilterColumns, coverage, where
from criciq_api.schemas.common import Coverage, Filters


@pytest.fixture(scope="module")
def db(fixture_serving_db: Path) -> Database:
    return Database(fixture_serving_db)


def test_no_filters_match_everything() -> None:
    assert where(Filters()) == ("TRUE", [])


def test_filters_travel_as_parameters() -> None:
    clause, params = where(
        Filters(season_from=2010, season_to=2019, team="MI'; DROP TABLE x;--", innings=2)
    )
    assert clause == "season >= ? AND season <= ? AND team_id = ? AND innings_no = ?"
    assert params == [2010, 2019, "MI'; DROP TABLE x;--", 2]
    assert "DROP" not in clause


def test_filters_follow_the_table_columns() -> None:
    columns = FilterColumns(team="batting_id", opponent="bowling_id", venue="m.venue_id")
    clause, params = where(Filters(team="CSK", opponent="MI", venue="wankhede"), columns)
    assert clause == "batting_id = ? AND bowling_id = ? AND m.venue_id = ?"
    assert params == ["CSK", "MI", "wankhede"]


def test_a_filter_without_a_column_is_an_error() -> None:
    with pytest.raises(ValueError, match="venue"):
        where(Filters(venue="x"), FilterColumns(venue=None))


def test_filters_run_against_the_data(db: Database) -> None:
    every = db.scalar("SELECT count(*) FROM player_batting_innings")
    clause, params = where(Filters(innings=1))
    first = db.scalar(f"SELECT count(*) FROM player_batting_innings WHERE {clause}", params)
    assert 0 < first < every


def test_coverage(db: Database) -> None:
    found = Coverage(**coverage(db))
    assert found.matches == db.scalar("SELECT count(*) FROM matches")
    assert found.first_season is not None
    assert found.last_season is not None
    assert found.first_season <= found.last_season
    assert found.first_season_label == str(found.first_season)
    assert found.first_date is not None
    assert found.last_date is not None
    assert found.first_date <= found.last_date
