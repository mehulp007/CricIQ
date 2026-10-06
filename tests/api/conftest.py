from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from criciq_api.core.config import Settings
from criciq_api.main import create_app


@pytest.fixture(scope="session")
def client(
    fixture_scored_serving_db: Path, fixture_scored_players_db: Path
) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        serving_db=fixture_scored_serving_db,
        players_db=fixture_scored_players_db,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def unscored_client(fixture_serving_db: Path) -> Iterator[TestClient]:
    """An API over data that was never scored by a model, without a players database."""
    settings = Settings(
        environment="test",
        serving_db=fixture_serving_db,
        players_db=fixture_serving_db.with_name("no-players.duckdb"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
