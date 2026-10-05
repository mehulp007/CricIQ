from typing import Any

from fastapi.testclient import TestClient


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_overview(client: TestClient) -> None:
    data = get(client, "/api/v1/teams")
    ids = [f["franchise_id"] for f in data["franchises"]]
    assert {"MI", "CSK", "KKR", "RCB"} <= set(ids)
    actives = [f["is_active"] for f in data["franchises"]]
    assert actives == sorted(actives, reverse=True), "current franchises come first"
    mi = next(f for f in data["franchises"] if f["franchise_id"] == "MI")
    assert 2019 in mi["titles"]
    assert 2019 in mi["finals"]
    assert 2019 in mi["playoffs"]
    rec = mi["record"]
    assert rec["played"] == rec["won"] + rec["lost"] + rec["no_result"]
    champions = {c["season"]: c["champion"]["franchise_id"] for c in data["champions"]}
    assert champions[2019] == "MI"
    assert champions[2023] == "CSK"
    league = data["league"]
    for key in ("chasing", "toss", "home", "close"):
        rate = league[key]
        if rate["total"]:
            assert rate["low"] <= rate["pct"] <= rate["high"]
    assert [s["season"] for s in league["seasons"]] == sorted(data["seasons"])


def test_standings(client: TestClient) -> None:
    table = get(client, "/api/v1/teams/standings/2019")
    assert table["season"] == 2019
    assert [r["position"] for r in table["rows"]] == list(range(1, len(table["rows"]) + 1))
    finishes = {r["team"]["franchise_id"]: r["finish"] for r in table["rows"]}
    assert finishes["MI"] == "champion"
    assert finishes["CSK"] == "runner_up"
    assert any(m["stage"] == "Final" for m in table["playoffs"])
    assert client.get("/api/v1/teams/standings/2099").status_code == 404


def test_team_profile(client: TestClient) -> None:
    data = get(client, "/api/v1/teams/csk")
    assert data["team"]["franchise_id"] == "CSK"
    team = data["team"]
    assert data["window"] == {"first": team["first_season"], "last": team["last_season"]}
    rec = data["record"]
    assert rec["played"] == rec["won"] + rec["lost"] + rec["no_result"]
    for group in data["splits"]:
        assert sum(s["record"]["played"] for s in group["splits"]) <= rec["played"]
    assert sum(o["record"]["played"] for o in data["opponents"]) == rec["played"]
    assert [p["phase"] for p in data["phases"]] == ["powerplay", "middle", "death"]
    for phase in data["phases"]:
        assert phase["batting"]["balls"] > 0
        assert phase["batting"]["par_run_rate"] is not None
    assert all(0 <= s["win_probability"] <= 1 for s in data["comebacks"] + data["collapses"])
    assert all(s["win_probability"] < 0.5 for s in data["comebacks"])
    seasons = [s["season"] for s in data["seasons"]]
    assert seasons == sorted(seasons)


def test_team_window_is_clipped_to_the_franchise(client: TestClient) -> None:
    gt = get(client, "/api/v1/teams/GT", **{"from": 2008, "to": 2030})
    assert gt["window"]["first"] >= 2022
    narrow = get(client, "/api/v1/teams/CSK", **{"from": 2023, "to": 2023})
    assert narrow["window"] == {"first": 2023, "last": 2023}


def test_team_errors(client: TestClient) -> None:
    assert client.get("/api/v1/teams/XYZ").status_code == 404
    assert client.get("/api/v1/teams/CSK", params={"from": 2025, "to": 2010}).status_code == 422


def test_head_to_head(client: TestClient) -> None:
    data = get(client, "/api/v1/teams/h2h", a="MI", b="CSK")
    rec = data["record"]
    assert rec["played"] == len(data["meetings"]) > 0
    assert rec["played"] == rec["a_won"] + rec["b_won"] + rec["no_result"]
    assert sum(s["record"]["played"] for s in data["seasons"]) == rec["played"]
    e = data["expectation"]
    assert e["low"] <= e["a_expected"] <= e["high"] <= e["decided"]
    assert e["a_won"] == rec["a_won"]
    flipped = get(client, "/api/v1/teams/h2h", a="CSK", b="MI")
    assert flipped["record"]["a_won"] == rec["b_won"]
    assert flipped["expectation"]["a_expected"] == round(e["decided"] - e["a_expected"], 1)


def test_head_to_head_errors(client: TestClient) -> None:
    assert client.get("/api/v1/teams/h2h", params={"a": "MI", "b": "MI"}).status_code == 422
    assert client.get("/api/v1/teams/h2h", params={"a": "MI", "b": "XYZ"}).status_code == 404
    never = get(client, "/api/v1/teams/h2h", a="MI", b="CSK", **{"from": 2008, "to": 2008})
    assert never["record"]["played"] == 0
    assert never["expectation"] is None


def test_unscored_data_has_no_swings(unscored_client: TestClient) -> None:
    data = get(unscored_client, "/api/v1/teams/MI")
    assert data["comebacks"] == []
    assert data["collapses"] == []
