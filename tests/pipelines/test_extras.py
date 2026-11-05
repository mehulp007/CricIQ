"""Extra tables added to a built serving database, keeping its model scores."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from criciq_core.publish import pending
from criciq_pipelines.extras import (
    EXTRAS,
    Extra,
    add_extras,
    build_extras,
    extend_database,
    has_scores,
)

# Two stand-in extras: one built from the balls, one from the model scores.
BALLS = Extra(
    "balls per innings",
    ("extra_innings_balls",),
    lambda con: con.execute(
        "CREATE TABLE extra_innings_balls AS SELECT match_id, innings_no, count(*) AS balls "
        "FROM deliveries GROUP BY ALL"
    ),
)
SCORED = Extra(
    "scored balls",
    ("extra_scored",),
    lambda con: con.execute(
        "CREATE TABLE extra_scored AS SELECT match_id, count(*) AS balls "
        "FROM wp_predictions GROUP BY ALL"
    ),
    needs_scores=True,
)
TEST_EXTRAS = (BALLS, SCORED)


def _tables(path: Path) -> set[str]:
    with duckdb.connect(str(path), read_only=True) as con:
        return {
            r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()
        }


def _rows(path: Path, table: str) -> int:
    with duckdb.connect(str(path), read_only=True) as con:
        return int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # type: ignore[index]


@pytest.fixture
def unscored(fixture_serving_db: Path, tmp_path: Path) -> Path:
    target = tmp_path / "unscored" / "serving.duckdb"
    target.parent.mkdir()
    shutil.copyfile(fixture_serving_db, target)
    return target


@pytest.fixture
def scored(fixture_scored_serving_db: Path, tmp_path: Path) -> Path:
    target = tmp_path / "scored" / "serving.duckdb"
    target.parent.mkdir()
    shutil.copyfile(fixture_scored_serving_db, target)
    return target


def test_every_extra_names_its_tables_once() -> None:
    tables = [t for extra in EXTRAS for t in extra.tables]
    assert len(tables) == len(set(tables))


def test_the_export_builds_the_registered_extras(fixture_serving_db: Path) -> None:
    built = _tables(fixture_serving_db)
    for extra in EXTRAS:
        if not extra.needs_scores:
            assert set(extra.tables) <= built


def test_an_unscored_database_gets_only_the_extras_that_need_no_scores(unscored: Path) -> None:
    notes: list[str] = []
    counts = extend_database(unscored, extras=TEST_EXTRAS, log=notes.append)
    assert set(counts) == {"extra_innings_balls"}
    assert counts["extra_innings_balls"] > 0
    assert "extra_scored" not in _tables(unscored)
    assert any("scored balls" in n for n in notes)


def test_a_scored_database_keeps_its_scores_and_gains_every_extra(scored: Path) -> None:
    before = _rows(scored, "wp_predictions")
    counts = extend_database(scored, extras=TEST_EXTRAS)
    assert set(counts) == {"extra_innings_balls", "extra_scored"}
    assert _rows(scored, "wp_predictions") == before
    assert counts["extra_scored"] == _rows(scored, "extra_scored")


def test_only_scored_skips_the_extras_the_export_already_built(scored: Path) -> None:
    counts = extend_database(scored, only_scored=True, extras=TEST_EXTRAS)
    assert set(counts) == {"extra_scored"}


def test_rebuilding_replaces_the_tables(scored: Path) -> None:
    first = extend_database(scored, extras=TEST_EXTRAS)
    again = extend_database(scored, extras=TEST_EXTRAS)
    assert again == first


def test_add_extras_publishes_a_copy(scored: Path) -> None:
    counts = add_extras(scored, extras=TEST_EXTRAS)
    assert counts["extra_scored"] > 0
    assert {"extra_innings_balls", "extra_scored"} <= _tables(scored)
    assert not pending(scored).exists()
    assert not scored.with_name(scored.name + ".extras").exists()


def test_add_extras_waits_beside_a_database_in_use(scored: Path) -> None:
    reader = duckdb.connect(str(scored), read_only=True)
    try:
        add_extras(scored, extras=TEST_EXTRAS)
    finally:
        reader.close()
    # Windows can't replace an open file, so the new version waits as `.next`;
    # elsewhere it replaces the file directly.
    newest = pending(scored) if pending(scored).exists() else scored
    assert "extra_scored" in _tables(newest)


def test_has_scores(unscored: Path, scored: Path) -> None:
    with duckdb.connect(str(unscored), read_only=True) as con:
        assert not has_scores(con)
    with duckdb.connect(str(scored), read_only=True) as con:
        assert has_scores(con)


def test_build_extras_on_an_open_connection(unscored: Path) -> None:
    with duckdb.connect(str(unscored)) as con:
        counts = build_extras(con, extras=(BALLS,))
    assert counts == {"extra_innings_balls": _rows(unscored, "extra_innings_balls")}
