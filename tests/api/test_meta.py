from fastapi.testclient import TestClient

from criciq_api import __version__
from criciq_api.main import create_app

client = TestClient(create_app())


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_meta_reports_versions() -> None:
    body = client.get("/api/v1/meta").json()
    assert body["api_version"] == "v1"
    assert body["app_version"] == __version__
    assert body["data_version"] is None
    assert body["model_versions"] == {}


def test_openapi_is_versioned() -> None:
    spec = client.get("/openapi.json").json()
    assert "/api/v1/meta" in spec["paths"]
