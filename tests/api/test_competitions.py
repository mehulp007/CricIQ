"""/api/v2: Player Lab for every T20 competition and all T20, over the fixture matches."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

T20 = ["ipl", "bbl", "psl", "cpl", "sa20", "t20i", "t20"]


def _get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_competitions_list_their_seasons(client: TestClient) -> None:
    response = client.get("/api/v2/competitions")
    assert response.status_code == 200
    assert response.headers["X-Data-Version"] == response.json()["data_version"]
    items = {c["id"]: c for c in response.json()["items"]}
    assert list(items) == T20
    assert items["t20"]["competitions"] == ["IPL", "BBL", "PSL", "CPL", "SA20", "T20I"]
    assert {"year": 2024, "label": "2023/24"} in items["bbl"]["seasons"]
    assert {"year": 2008, "label": "2008"} in items["ipl"]["seasons"]
    assert items["t20"]["matches"] == sum(items[c]["matches"] for c in T20[:-1])
    assert all(items[c]["players"] > 0 for c in T20)


def test_every_competition_has_a_directory_profile_and_splits(client: TestClient) -> None:
    for competition in T20:
        page = _get(client, f"/api/v2/{competition}/players", sort="runs", page_size=5)
        assert page["total"] > 0
        busiest = page["items"][0]
        assert busiest["team"]["color"]
        profile = _get(client, f"/api/v2/{competition}/players/{busiest['player_id']}")
        assert profile["player"]["player_id"] == busiest["player_id"]
        assert profile["batting"]["runs"] == busiest["runs"]
        assert profile["batting"]["par_strike_rate"] is not None
        # Ratings and win probability added come with the pooled T20 models.
        assert profile["ratings"] == {"batting": None, "bowling": None}
        splits = _get(client, f"/api/v2/{competition}/players/{busiest['player_id']}/splits")
        assert [g["key"] for g in splits["batting"]][:2] == ["phase", "bowling_type"]


def test_all_t20_adds_up_a_players_competitions(client: TestClient) -> None:
    lines: dict[str, list[dict[str, Any]]] = {}
    for competition in T20[:-1]:
        page = _get(client, f"/api/v2/{competition}/players", page_size=100)
        for item in page["items"]:
            lines.setdefault(item["player_id"], []).append(item)
    player_id, played = next((p, items) for p, items in lines.items() if len(items) > 1)
    whole = _get(client, f"/api/v2/t20/players/{player_id}")
    assert whole["player"]["matches"] == sum(i["matches"] for i in played)
    assert whole["batting"]["runs"] == sum(i["runs"] for i in played)

    careers = _get(client, f"/api/v2/players/{player_id}")
    assert [c["competition"] for c in careers["careers"]][-1] == "t20"
    assert len(careers["careers"]) == len(played) + 1
    assert careers["careers"][-1]["matches"] == whole["player"]["matches"]
    assert careers["careers"][-1]["runs"] == whole["batting"]["runs"]


def test_a_bbl_season_is_filtered_by_its_year(client: TestClient) -> None:
    page = _get(client, "/api/v2/bbl/players", season=2024, page_size=100)
    assert page["total"] > 0
    assert _get(client, "/api/v2/bbl/players", season=2023)["total"] == 0


def test_unknown_competitions_and_players_are_not_found(client: TestClient) -> None:
    assert client.get("/api/v2/odi/players").status_code == 404
    assert client.get("/api/v2/bbl/players/nobody").status_code == 404
    assert client.get("/api/v2/players/nobody").status_code == 404
    assert client.get("/api/v2/BBL/players").status_code == 422  # lower-case ids only


def test_without_a_players_database_v2_is_unavailable(unscored_client: TestClient) -> None:
    assert unscored_client.get("/api/v2/competitions").status_code == 503
    assert unscored_client.get("/api/v1/players").status_code == 200
