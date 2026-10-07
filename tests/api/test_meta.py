import shutil
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from criciq_api import __version__
from criciq_api.core.config import Settings
from criciq_api.db import Database, ServingDataMissingError
from criciq_api.main import create_app
from criciq_core import publish
from criciq_ml import registry


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_meta_reports_dataset(client: TestClient) -> None:
    response = client.get("/api/v2/ipl/meta")
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["app_version"] == __version__
    assert body["data_version"].startswith("2025-06-03.")
    assert response.headers["X-Data-Version"] == body["data_version"]
    # The versions serving the IPL (the pooled T20 versions where the IPL takes them).
    assert body["model_versions"] == {
        name: registry.current_version(name, "IPL")
        for name in (
            "ball_outcome",
            "ratings",
            "score_projection",
            "simulator",
            "win_probability",
        )
    }
    assert {s["year"] for s in body["seasons"]} >= {2008, 2019, 2025}
    franchise_ids = {f["franchise_id"] for f in body["franchises"]}
    assert {"MI", "CSK", "DC", "DCH"} <= franchise_ids
    assert all(v["matches"] >= 0 for v in body["venues"])


def test_openapi_is_versioned(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    found = set(spec["paths"])
    assert {
        "/api/v2/{competition}/meta",
        "/api/v2/{competition}/matches",
        "/api/v2/{competition}/matches/{match_id}/timeline",
        "/api/v2/{competition}/players/{player_id}",
    } <= found
    # v1 lives on only on the main branch's live API.
    assert not any(path.startswith("/api/v1") for path in found)


def test_missing_serving_database_fails_fast(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        serving_db=tmp_path / "absent.duckdb",
        players_db=tmp_path / "no-players.duckdb",
    )
    with (
        pytest.raises(ServingDataMissingError, match="criciq-data"),
        TestClient(create_app(settings)),
    ):
        pass


def test_database_knows_its_format(fixture_serving_db: Path) -> None:
    # Phase labels and splits follow the served competition's format.
    db = Database(fixture_serving_db)
    try:
        assert db.match_format == "T20"
    finally:
        db.close()


def test_meta_has_no_model_versions_before_scoring(unscored_client: TestClient) -> None:
    assert unscored_client.get("/api/v2/ipl/meta").json()["model_versions"] == {}


def test_meta_reports_the_latest_data_update(
    fixture_scored_serving_db: Path, tmp_path: Path
) -> None:
    serving = tmp_path / "serving.duckdb"
    shutil.copyfile(fixture_scored_serving_db, serving)
    con = duckdb.connect(str(serving))
    con.execute(
        """
        INSERT INTO data_updates VALUES
            (1, '2026-10-01 06:00', 'initial', 'IPL', 14, 0, 0, 0),
            (3, '2027-04-02 06:00', 'sync', 'IPL', 2, 1, 0, 1),
            (4, '2027-04-03 06:00', 'sync', 'IPL', 0, 0, 0, 1)
        """
    )
    con.close()
    settings = Settings(
        environment="test", serving_db=serving, players_db=serving.with_name("no-players.duckdb")
    )
    with TestClient(create_app(settings)) as client:
        body = client.get("/api/v2/ipl/meta").json()
    assert body["last_update"] == {
        "updated_at": "2027-04-02T06:00:00",
        "new_matches": 2,
        "corrected_matches": 1,
        "withdrawn_matches": 0,
    }
    assert body["latest_match_date"] == "2025-06-03"


def test_meta_has_no_update_after_only_the_first_load(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/meta").json()["last_update"] is None


def test_the_api_swaps_in_newly_published_data(
    fixture_scored_serving_db: Path, tmp_path: Path
) -> None:
    serving = tmp_path / "serving.duckdb"
    shutil.copyfile(fixture_scored_serving_db, serving)
    db = Database(serving)
    try:
        db.cache["stale"] = object()
        assert db.refresh(force=True) is False  # nothing waiting
        newer = publish.pending(serving)
        shutil.copyfile(fixture_scored_serving_db, newer)
        con = duckdb.connect(str(newer))
        con.execute("UPDATE meta SET value = 'newer' WHERE key = 'data_version'")
        con.close()
        assert db.refresh(force=True) is True
        assert db.data_version == "newer"
        assert db.cache == {}
        assert not newer.exists()
        assert db.scalar("SELECT count(*) FROM matches") > 0
    finally:
        db.close()


def test_data_published_while_the_api_was_down_is_used_at_startup(
    fixture_scored_serving_db: Path, tmp_path: Path
) -> None:
    serving = tmp_path / "serving.duckdb"
    shutil.copyfile(fixture_scored_serving_db, serving)
    newer = publish.pending(serving)
    shutil.copyfile(fixture_scored_serving_db, newer)
    con = duckdb.connect(str(newer))
    con.execute("UPDATE meta SET value = 'newer' WHERE key = 'data_version'")
    con.close()
    db = Database(serving)
    try:
        assert db.data_version == "newer"
        assert not newer.exists()
    finally:
        db.close()
