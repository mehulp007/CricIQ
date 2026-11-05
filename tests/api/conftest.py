import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from criciq_api.core.config import Settings
from criciq_api.main import create_app
from criciq_pipelines.notes import build_notes


@pytest.fixture(scope="session")
def fixture_notes_db(
    fixture_scored_serving_db: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """The daily notes of the scored fixture databases (the IPL, T20Is, ODIs and Tests)."""
    folder = fixture_scored_serving_db.parent
    out = tmp_path_factory.mktemp("notes") / "notes.duckdb"
    build_notes(
        {
            c: folder / ("serving.duckdb" if c == "IPL" else f"serving-{c.lower()}.duckdb")
            for c in ("IPL", "T20I", "ODI", "TEST")
        },
        out,
        built=dt.datetime(2026, 1, 1, 12, 0),
    )
    return out


@pytest.fixture(scope="session")
def client(
    fixture_scored_serving_db: Path, fixture_scored_players_db: Path, fixture_notes_db: Path
) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        serving_db=fixture_scored_serving_db,
        players_db=fixture_scored_players_db,
        notes_db=fixture_notes_db,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def unscored_client(fixture_serving_db: Path, fixture_players_db: Path) -> Iterator[TestClient]:
    """An API over data that was never scored by a model."""
    settings = Settings(
        environment="test",
        serving_db=fixture_serving_db,
        players_db=fixture_players_db,
        notes_db=fixture_serving_db.with_name("no-notes.duckdb"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def no_players_client(fixture_serving_db: Path) -> Iterator[TestClient]:
    """An API without a players database."""
    settings = Settings(
        environment="test",
        serving_db=fixture_serving_db,
        players_db=fixture_serving_db.with_name("no-players.duckdb"),
        notes_db=fixture_serving_db.with_name("no-notes.duckdb"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
