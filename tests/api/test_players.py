"""Player Lab endpoints over the fixture matches."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def _find(client: TestClient, q: str) -> dict[str, Any]:
    response = client.get("/api/v1/players", params={"q": q})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1, items
    item: dict[str, Any] = items[0]
    return item


def test_search_matches_name_tokens_in_any_order(client: TestClient) -> None:
    assert _find(client, "mccullum")["name"] == "BB McCullum"
    assert (
        _find(client, "Brendon McCullum")["player_id"] == _find(client, "mccullum b")["player_id"]
    )
    assert client.get("/api/v1/players", params={"q": "zzzz"}).json()["total"] == 0


def test_directory_sorts_and_paginates(client: TestClient) -> None:
    page = client.get("/api/v1/players", params={"sort": "runs", "page_size": 5}).json()
    runs = [p["runs"] for p in page["items"]]
    assert runs == sorted(runs, reverse=True)
    assert page["total"] > 5
    second = client.get(
        "/api/v1/players", params={"sort": "runs", "page_size": 5, "page": 2}
    ).json()
    assert not {p["player_id"] for p in page["items"]} & {p["player_id"] for p in second["items"]}


def test_directory_filters_scope_the_numbers(client: TestClient) -> None:
    everyone = client.get("/api/v1/players", params={"page_size": 100}).json()
    mi_2019 = client.get(
        "/api/v1/players", params={"season": 2019, "team": "mi", "page_size": 100}
    ).json()
    assert 11 <= mi_2019["total"] < everyone["total"]
    assert all(p["team"]["franchise_id"] == "MI" for p in mi_2019["items"])
    bumrah = next(p for p in mi_2019["items"] if p["name"] == "JJ Bumrah")
    assert bumrah["wickets"] == 2
    assert bumrah["economy"] == 3.5
    bowlers = client.get("/api/v1/players", params={"role": "bowler", "page_size": 100}).json()
    assert bowlers["items"]
    assert all(p["role"] == "bowler" for p in bowlers["items"])


def test_directory_rejects_bad_parameters(client: TestClient) -> None:
    assert client.get("/api/v1/players", params={"role": "captain"}).status_code == 422
    assert client.get("/api/v1/players", params={"sort": "age"}).status_code == 422
    assert client.get("/api/v1/players", params={"page_size": 500}).status_code == 422


def test_profile_reads_like_a_career_record(client: TestClient) -> None:
    player = _find(client, "mccullum")
    profile = client.get(f"/api/v1/players/{player['player_id']}").json()
    batting = profile["batting"]
    assert profile["player"]["name"] == "BB McCullum"
    assert batting["highest"]["runs"] == 158
    assert batting["highest"]["not_out"]
    assert batting["hundreds"] >= 1
    # Seasons and phases partition the same runs.
    assert sum(s["batting"]["runs"] for s in profile["seasons"] if s["batting"]) == batting["runs"]
    assert sum(p["runs"] for p in profile["phases"]["batting"]) == batting["runs"]
    assert sum(p["share"] for p in profile["phases"]["batting"]) == pytest.approx(1, abs=1e-3)
    assert batting["strike_rate"] == round(100 * batting["runs"] / batting["balls"], 2)
    assert batting["runs_above_par"] == pytest.approx(
        batting["runs"] - batting["par_strike_rate"] * batting["balls"] / 100, abs=0.1
    )
    assert profile["recent"]["batting"][0]["runs"] >= 0
    assert batting["wpa"] is not None
    assert batting["wpa_innings"] > 0


def test_bowling_profile(client: TestClient) -> None:
    bumrah = _find(client, "bumrah")
    profile = client.get(f"/api/v1/players/{bumrah['player_id']}").json()
    bowling = profile["bowling"]
    assert bowling["best"]["wickets"] >= 2
    assert bowling["overs"] == f"{bowling['balls'] // 6}.{bowling['balls'] % 6}"
    assert sum(d["count"] for d in profile["dismissals"]["bowling"]) == bowling["wickets"]
    assert profile["player"]["role"] == "bowler"
    assert profile["player"]["teams"][0]["franchise_id"] == "MI"


def test_season_window_narrows_everything(client: TestClient) -> None:
    bumrah = _find(client, "bumrah")["player_id"]
    full = client.get(f"/api/v1/players/{bumrah}").json()
    final = client.get(f"/api/v1/players/{bumrah}", params={"from": 2019, "to": 2019}).json()
    assert final["window"] == {"first": 2019, "last": 2019}
    assert [s["season"] for s in final["seasons"]] == [2019]
    assert final["bowling"]["wickets"] <= full["bowling"]["wickets"]
    assert (
        client.get(f"/api/v1/players/{bumrah}", params={"from": 2020, "to": 2019}).status_code
        == 422
    )


def test_percentiles_rank_only_qualified_players(client: TestClient) -> None:
    # The fixtures are a handful of matches, so nobody reaches the 300-ball bar.
    mccullum = _find(client, "mccullum")["player_id"]
    group = client.get(f"/api/v1/players/{mccullum}").json()["percentiles"]["batting"]
    assert group["qualified"] is False
    assert all(item["percentile"] is None for item in group["items"])
    assert {i["key"] for i in group["items"]} >= {"strike_rate", "average", "death", "wpa"}


def test_splits_partition_the_totals(client: TestClient) -> None:
    player = _find(client, "mccullum")["player_id"]
    profile = client.get(f"/api/v1/players/{player}").json()
    splits = client.get(f"/api/v1/players/{player}/splits").json()
    groups = {g["key"]: g for g in splits["batting"]}
    assert {"phase", "bowling_type", "position", "innings", "opposition", "venue", "season"} <= set(
        groups
    )
    for group in groups.values():
        assert sum(r["runs"] for r in group["rows"]) == profile["batting"]["runs"], group["key"]
        assert sum(r["balls"] for r in group["rows"]) == profile["batting"]["balls"], group["key"]
    assert groups["phase"]["rows"][0]["innings"] is None
    assert groups["venue"]["rows"][0]["innings"] >= 1
    assert all(r["label"].startswith("vs ") for r in groups["opposition"]["rows"])
    assert all(r["color"] for r in groups["opposition"]["rows"])


def test_unknown_player_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/players/not-a-player").status_code == 404
    assert client.get("/api/v1/players/not-a-player/splits").status_code == 404


def test_profile_without_model_scores(unscored_client: TestClient) -> None:
    player = _find(unscored_client, "mccullum")["player_id"]
    profile = unscored_client.get(f"/api/v1/players/{player}").json()
    assert profile["batting"]["wpa"] is None
    assert profile["recent"]["batting"][0]["wpa"] is None
    assert "wpa" not in {i["key"] for i in profile["percentiles"]["batting"]["items"]}
