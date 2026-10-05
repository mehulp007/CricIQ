from typing import Any

from fastapi.testclient import TestClient


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _request(client: TestClient, **extra: Any) -> dict[str, Any]:
    mi = get(client, "/api/v1/simulate/xi/MI")
    csk = get(client, "/api/v1/simulate/xi/CSK")
    return {
        "a": {"franchise_id": "MI", "batters": [p["player_id"] for p in mi["players"]]},
        "b": {"franchise_id": "CSK", "batters": [p["player_id"] for p in csk["players"]]},
        "simulations": 1000,
        **extra,
    }


def test_latest_xi(client: TestClient) -> None:
    xi = get(client, "/api/v1/simulate/xi/MI")
    assert xi["team"]["franchise_id"] == "MI"
    assert len(xi["players"]) == 11
    assert len(xi["bowlers"]) >= 5
    ids = {p["player_id"] for p in xi["players"]}
    assert set(xi["bowlers"]) <= ids
    assert client.get("/api/v1/simulate/xi/XYZ").status_code == 404


def test_order_any_players(client: TestClient) -> None:
    xi = get(client, "/api/v1/simulate/xi/MI")
    ids = [p["player_id"] for p in xi["players"]][::-1]
    ordered = post(client, "/api/v1/simulate/xi", {"player_ids": ids})
    assert {p["player_id"] for p in ordered["players"]} == set(ids)
    assert (
        client.post("/api/v1/simulate/xi", json={"player_ids": ["nobody", ids[0]]}).status_code
        == 404
    )
    assert (
        client.post("/api/v1/simulate/xi", json={"player_ids": [ids[0], ids[0]]}).status_code == 422
    )


def test_simulate_match(client: TestClient) -> None:
    body = _request(client)
    result = post(client, "/api/v1/simulate/match", body)
    assert result["label"] == "Model simulation"
    total = result["a_win_pct"] + result["b_win_pct"] + result["tie_pct"]
    assert abs(total - 100) < 0.2
    a, b = result["sides"]
    assert {a["key"], b["key"]} == {"a", "b"}
    assert abs(a["batting_first_pct"] - 50) < 0.1  # the toss splits the simulations
    assert a["first_innings"]["p10"] <= a["first_innings"]["p50"] <= a["first_innings"]["p90"]
    assert len(a["batters"]) == 11
    overs = sum(bw["overs"] for bw in a["bowlers"])
    assert 15 < overs <= 20
    assert all(bw["overs"] <= 4 for bw in a["bowlers"])
    # The same request gets the same answer.
    again = post(client, "/api/v1/simulate/match", body)
    assert again["a_win_pct"] == result["a_win_pct"]


def test_simulate_match_with_a_chosen_batting_order(client: TestClient) -> None:
    result = post(client, "/api/v1/simulate/match", _request(client, bat_first="b", seed=3))
    a, b = result["sides"]
    assert a["first_innings"] is None
    assert b["batting_first_pct"] == 100.0
    assert a["chase_pct"] is not None


def test_simulate_match_rejects_bad_sides(client: TestClient) -> None:
    body = _request(client)
    short = {**body, "a": {**body["a"], "batters": body["a"]["batters"][:10]}}
    assert client.post("/api/v1/simulate/match", json=short).status_code == 422
    few = {**body, "a": {**body["a"], "bowlers": body["a"]["batters"][:4]}}
    assert client.post("/api/v1/simulate/match", json=few).status_code == 422
    stranger = {**body, "a": {**body["a"], "bowlers": body["b"]["batters"][:5]}}
    assert client.post("/api/v1/simulate/match", json=stranger).status_code == 422


def test_what_if_moves_the_model_estimate(client: TestClient) -> None:
    base = {"match_id": 1181768, "innings_no": 2, "seq_no": 100, "simulations": 1000}
    real = post(client, "/api/v1/simulate/state", base)
    assert real["label"] == "Model simulation"
    assert real["batting"]["franchise_id"] == "CSK"
    assert real["target"] == 150
    # No edit: the what-if is the model's own estimate.
    assert abs(real["whatif_win_pct"] - real["model_win_pct"]) < 0.11
    more = post(
        client, "/api/v1/simulate/state", {**base, "runs": real["actual"]["score"]["runs"] + 20}
    )
    assert more["whatif_win_pct"] > real["whatif_win_pct"]
    worse = post(client, "/api/v1/simulate/state", {**base, "wickets": 8})
    assert worse["edited"]["score"]["wickets"] == 8
    assert worse["whatif_win_pct"] < real["whatif_win_pct"]


def test_what_if_first_innings_and_errors(client: TestClient) -> None:
    start = post(
        client, "/api/v1/simulate/state", {"match_id": 1181768, "innings_no": 1, "seq_no": 0}
    )
    assert start["actual"]["score"] == {"runs": 0, "wickets": 0, "balls": 0}
    assert start["target"] is None
    assert 100 < start["actual"]["total"]["p50"] < 250
    missing = client.post(
        "/api/v1/simulate/state", json={"match_id": 1181768, "innings_no": 1, "seq_no": 9999}
    )
    assert missing.status_code == 404
    unknown = {"match_id": 1, "innings_no": 1, "seq_no": 0}
    assert client.post("/api/v1/simulate/state", json=unknown).status_code == 404


def test_unscored_data_has_no_simulator(client: TestClient, unscored_client: TestClient) -> None:
    # XIs need only the data; simulating needs the published models.
    assert unscored_client.get("/api/v1/simulate/xi/MI").status_code == 200
    body = _request(client)
    assert unscored_client.post("/api/v1/simulate/match", json=body).status_code == 503
