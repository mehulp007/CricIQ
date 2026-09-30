from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from criciq_api import __version__
from criciq_api.core.config import Settings
from criciq_api.db import ServingDataMissingError
from criciq_api.main import create_app


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_meta_reports_dataset(client: TestClient) -> None:
    response = client.get("/api/v1/meta")
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["app_version"] == __version__
    assert body["data_version"].startswith("2025-06-03.")
    assert response.headers["X-Data-Version"] == body["data_version"]
    assert body["model_versions"] == {}
    assert {s["year"] for s in body["seasons"]} >= {2008, 2019, 2025}
    franchise_ids = {f["franchise_id"] for f in body["franchises"]}
    assert {"MI", "CSK", "DC", "DCH"} <= franchise_ids
    assert all(v["matches"] >= 0 for v in body["venues"])


def test_openapi_is_versioned(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert {"/api/v1/meta", "/api/v1/matches", "/api/v1/matches/{match_id}/timeline"} <= set(
        spec["paths"]
    )


def test_missing_serving_database_fails_fast(tmp_path: Path) -> None:
    settings = Settings(environment="test", serving_db=tmp_path / "absent.duckdb")
    with (
        pytest.raises(ServingDataMissingError, match="criciq-data"),
        TestClient(create_app(settings)),
    ):
        pass
