"""The Records hub: every record's leader, ranked lists with ties, filters and paging."""

from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from criciq_api.db import Database
from criciq_api.repositories.records import RECORDS
from criciq_api.services import records as records_service
from criciq_api.services.records import RecordDataMissingError, get_hub


def _get(client: TestClient, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture(scope="module")
def hub(client: TestClient) -> dict[str, Any]:
    return _get(client, "/api/v2/ipl/records")


@pytest.fixture(scope="module")
def serving(fixture_scored_serving_db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(fixture_scored_serving_db), read_only=True)


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    found = con.execute(sql).fetchone()
    assert found is not None
    return found[0]


def test_the_hub_lists_each_record_with_its_leader(hub: dict[str, Any]) -> None:
    assert hub["format"] == "T20"
    assert hub["coverage"]["matches"] > 0
    keys = [lead["record"]["key"] for lead in hub["records"]]
    assert len(keys) == len(set(keys))
    for must in ("most-runs", "highest-scores", "highest-partnerships", "highest-totals"):
        assert must in keys
    # T20 has four-wicket innings and no innings wins.
    assert "most-four-wicket-innings" in keys
    assert "biggest-innings-wins" not in keys
    for lead in hub["records"]:
        assert lead["leaders"]
        assert all(e["rank"] == 1 for e in lead["leaders"])
        assert lead["tied_count"] >= len(lead["leaders"])
    assert hub["groups"][0] == "batting"


def test_leaders_match_the_scorecards(
    hub: dict[str, Any], serving: duckdb.DuckDBPyConnection
) -> None:
    lead = {r["record"]["key"]: r["leaders"][0] for r in hub["records"]}
    assert lead["highest-scores"]["value"] == _scalar(
        serving, "SELECT max(runs) FROM player_batting_innings"
    )
    assert lead["most-runs"]["value"] == _scalar(
        serving,
        "SELECT max(r) FROM (SELECT sum(runs) AS r FROM player_batting_innings GROUP BY player_id)",
    )
    assert lead["highest-totals"]["value"] == _scalar(
        serving, "SELECT max(runs) FROM innings WHERE NOT is_super_over"
    )
    assert lead["highest-partnerships"]["value"] == _scalar(
        serving, "SELECT max(runs) FROM partnerships"
    )
    best = serving.execute(
        "SELECT wickets, runs FROM player_bowling_innings ORDER BY wickets DESC, runs LIMIT 1"
    ).fetchone()
    assert best is not None
    assert lead["best-bowling-figures"]["display"] == f"{best[0]}/{best[1]}"


@pytest.mark.parametrize("record", [r for r in RECORDS if "T20" in r.formats], ids=lambda r: r.key)
def test_every_t20_record_lists_its_entries_in_order(client: TestClient, record: Any) -> None:
    body = _get(client, f"/api/v2/ipl/records/{record.key}", limit=50)
    assert body["record"]["key"] == record.key
    values = [e["value"] for e in body["entries"]]
    assert values == sorted(values, reverse=not record.ascending)
    for a, b in zip(body["entries"], body["entries"][1:], strict=False):
        assert (a["value"] == b["value"]) == (a["rank"] == b["rank"])
        if a["value"] == b["value"]:
            assert a["tied"]
            assert b["tied"]
    assert len(body["record"]["columns"]) == len(body["entries"][0]["figures"]) if values else True
    assert body["total"] >= len(body["entries"])


def test_tests_have_their_own_records(client: TestClient) -> None:
    body = _get(client, "/api/v2/test/records")
    keys = {lead["record"]["key"] for lead in body["records"]}
    assert "biggest-innings-wins" in keys or not body["records"]
    assert "best-economy-in-an-innings" not in keys
    assert "most-four-wicket-innings" not in keys
    wins = _get(client, "/api/v2/test/records/biggest-wins-by-wickets")
    assert wins["record"]["columns"] == []
    if wins["entries"]:
        assert wins["entries"][0]["figures"] == []


def test_paging_continues_the_ranks(client: TestClient) -> None:
    whole = _get(client, "/api/v2/ipl/records/highest-scores", limit=10)
    page = _get(client, "/api/v2/ipl/records/highest-scores", limit=5, offset=5)
    assert page["total"] == whole["total"]
    assert page["offset"] == 5
    assert [e["value"] for e in page["entries"]] == [e["value"] for e in whole["entries"][5:10]]
    assert [e["rank"] for e in page["entries"]] == [e["rank"] for e in whole["entries"][5:10]]


def test_filters_narrow_the_lists(client: TestClient, hub: dict[str, Any]) -> None:
    team = next(r for r in hub["records"] if r["record"]["key"] == "most-runs")["leaders"][0]
    franchise = team["team"]["franchise_id"]
    mine = _get(client, "/api/v2/ipl/records/highest-scores", team=franchise)
    assert mine["filters"]["team"] == franchise
    assert all(e["team"]["franchise_id"] == franchise for e in mine["entries"])
    against = _get(client, "/api/v2/ipl/records/highest-scores", opponent=franchise)
    assert all(e["opponent"]["franchise_id"] == franchise for e in against["entries"])
    first = _get(client, "/api/v2/ipl/records/highest-partnerships", wicket=1)
    assert all(e["figures"][0]["value"] == "1" for e in first["entries"])
    none = _get(client, "/api/v2/ipl/records/most-runs", team="ZZZ")
    assert none["entries"] == []
    assert none["total"] == 0


def test_entries_link_to_the_match_and_ball(client: TestClient) -> None:
    stands = _get(client, "/api/v2/ipl/records/highest-partnerships", limit=3)["entries"]
    assert stands
    stand = stands[0]
    assert len(stand["players"]) == 2
    assert stand["match_id"] is not None
    assert stand["ball"] is not None
    innings, seq = stand["ball"].split(".")
    assert int(innings) >= 1
    assert int(seq) >= 0
    swings = _get(client, "/api/v2/ipl/records/biggest-win-probability-swings", limit=1)
    assert swings["record"]["model"] is True
    entry = swings["entries"][0]
    assert [p["role"] for p in entry["players"]] == ["batter", "bowler"]
    assert entry["display"].endswith(" pts")


def test_qualifications_are_stated(client: TestClient) -> None:
    body = _get(client, "/api/v2/ipl/records/best-batting-average")
    # The fixtures are a small dataset, so everyone qualifies.
    assert body["record"]["qualification"] == "At least 1 innings"
    assert _get(client, "/api/v2/ipl/records/most-runs")["record"]["qualification"] is None


def test_bad_requests(client: TestClient, unscored_client: TestClient) -> None:
    assert client.get("/api/v2/ipl/records/no-such-record").status_code == 404
    assert client.get("/api/v2/ipl/records/biggest-innings-wins").status_code == 404
    assert client.get("/api/v2/ipl/records/most-runs", params={"wicket": 2}).status_code == 422
    assert (
        client.get("/api/v2/ipl/records/most-runs", params={"from": 2020, "to": 2010}).status_code
        == 422
    )
    assert client.get("/api/v2/ipl/records/most-runs", params={"limit": 601}).status_code == 422
    # Model records need a scored database.
    assert (
        unscored_client.get("/api/v2/ipl/records/biggest-win-probability-swings").status_code == 404
    )
    assert unscored_client.get("/api/v2/ipl/records/most-runs").status_code == 200


def test_a_build_without_record_tables_says_so(fixture_serving_db: Path, tmp_path: Path) -> None:
    older = tmp_path / "serving.duckdb"
    shutil.copyfile(fixture_serving_db, older)
    with duckdb.connect(str(older)) as con:
        con.execute("DROP TABLE partnerships")
    with pytest.raises(RecordDataMissingError, match="criciq-data extras"):
        get_hub(Database(older))


def test_the_sites_list_of_records_matches_the_api() -> None:
    """frontend/lib/record-keys.json (the sitemap's record pages) follows the catalog."""
    keys = json.loads(
        (Path(__file__).resolve().parents[2] / "frontend" / "lib" / "record-keys.json").read_text(
            "utf-8"
        )
    )
    expected = {f: [r.key for r in RECORDS if f in r.formats] for f in ("T20", "ODI", "Test")}
    assert keys == expected, "regenerate frontend/lib/record-keys.json from the record catalog"


def test_concurrent_requests_build_a_hub_once(
    fixture_scored_serving_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A burst of hub requests (a build rendering every page at once) builds it one time."""
    db = Database(fixture_scored_serving_db)
    built: list[int] = []
    real = records_service._build_hub

    def counted(database: Database) -> Any:
        built.append(1)
        time.sleep(0.2)  # long enough for the others to arrive while it builds
        return real(database)

    monkeypatch.setattr(records_service, "_build_hub", counted)
    with ThreadPoolExecutor(max_workers=8) as pool:
        hubs = list(pool.map(lambda _: records_service.get_hub(db), range(8)))
    assert len(built) == 1
    assert all(h is hubs[0] for h in hubs)


def test_a_player_s_records_held(client: TestClient) -> None:
    top = client.get("/api/v2/ipl/records/most-runs").json()["entries"][0]
    player = top["players"][0]["player_id"]
    held = client.get(f"/api/v2/ipl/records/players/{player}")
    assert held.status_code == 200
    body = held.json()
    assert body["player_id"] == player
    most = next(h for h in body["records"] if h["record"]["key"] == "most-runs")
    assert most["entries"][0]["rank"] == 1
    ranks = [min(e["rank"] for e in h["entries"]) for h in body["records"]]
    assert ranks == sorted(ranks)
    assert all(e["rank"] <= 10 for h in body["records"] for e in h["entries"])
    assert all(h["record"]["group"] != "teams" for h in body["records"])
    assert client.get("/api/v2/ipl/records/players/nobody").json()["records"] == []
    assert client.get("/api/v2/ipl/records/players/bad%20id").status_code == 422
