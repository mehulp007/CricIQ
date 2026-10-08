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
    mi = get(client, "/api/v2/ipl/simulate/xi/MI")
    csk = get(client, "/api/v2/ipl/simulate/xi/CSK")
    return {
        "a": {"franchise_id": "MI", "batters": [p["player_id"] for p in mi["players"]]},
        "b": {"franchise_id": "CSK", "batters": [p["player_id"] for p in csk["players"]]},
        "simulations": 1000,
        **extra,
    }


def test_latest_xi(client: TestClient) -> None:
    xi = get(client, "/api/v2/ipl/simulate/xi/MI")
    assert xi["team"]["franchise_id"] == "MI"
    assert len(xi["players"]) == 11
    assert len(xi["bowlers"]) >= 5
    ids = {p["player_id"] for p in xi["players"]}
    assert set(xi["bowlers"]) <= ids
    assert client.get("/api/v2/ipl/simulate/xi/XYZ").status_code == 404


def test_order_any_players(client: TestClient) -> None:
    xi = get(client, "/api/v2/ipl/simulate/xi/MI")
    ids = [p["player_id"] for p in xi["players"]][::-1]
    ordered = post(client, "/api/v2/ipl/simulate/xi", {"player_ids": ids})
    assert {p["player_id"] for p in ordered["players"]} == set(ids)
    assert (
        client.post("/api/v2/ipl/simulate/xi", json={"player_ids": ["nobody", ids[0]]}).status_code
        == 404
    )
    assert (
        client.post("/api/v2/ipl/simulate/xi", json={"player_ids": [ids[0], ids[0]]}).status_code
        == 422
    )


def test_simulate_match(client: TestClient) -> None:
    body = _request(client)
    result = post(client, "/api/v2/ipl/simulate/match", body)
    assert result["label"] == "Model simulation"
    total = result["a_win_pct"] + result["b_win_pct"] + result["tie_pct"]
    assert abs(total - 100) < 0.2
    a, b = result["sides"]
    assert {a["key"], b["key"]} == {"a", "b"}
    assert abs(a["batting_first_pct"] - 50) < 0.1  # the toss splits the simulations
    assert a["first_innings"]["p10"] <= a["first_innings"]["p50"] <= a["first_innings"]["p90"]
    assert len(a["batters"]) == 11
    # Scorecards are typical innings in whole runs, balls and wickets.
    opener = a["batters"][0]
    assert opener["batted_pct"] == 100.0
    assert all(isinstance(opener[k], int) for k in ("runs", "runs_low", "runs_high", "balls"))
    assert opener["runs_low"] <= opener["runs"] <= opener["runs_high"]
    for bw in a["bowlers"]:
        assert bw["balls"] is None or 0 < bw["balls"] <= 24
        assert bw["wickets"] is None or isinstance(bw["wickets"], int)
    assert sum(bw["bowled_pct"] for bw in a["bowlers"]) >= 400  # five bowlers or more
    # The same request gets the same answer.
    again = post(client, "/api/v2/ipl/simulate/match", body)
    assert again["a_win_pct"] == result["a_win_pct"]


def test_simulate_match_with_a_chosen_batting_order(client: TestClient) -> None:
    result = post(client, "/api/v2/ipl/simulate/match", _request(client, bat_first="b", seed=3))
    a, b = result["sides"]
    assert a["first_innings"] is None
    assert b["batting_first_pct"] == 100.0
    assert a["chase_pct"] is not None


def test_simulate_match_rejects_bad_sides(client: TestClient) -> None:
    body = _request(client)
    short = {**body, "a": {**body["a"], "batters": body["a"]["batters"][:10]}}
    assert client.post("/api/v2/ipl/simulate/match", json=short).status_code == 422
    few = {**body, "a": {**body["a"], "bowlers": body["a"]["batters"][:4]}}
    assert client.post("/api/v2/ipl/simulate/match", json=few).status_code == 422
    stranger = {**body, "a": {**body["a"], "bowlers": body["b"]["batters"][:5]}}
    assert client.post("/api/v2/ipl/simulate/match", json=stranger).status_code == 422


def test_seasons_and_squads(client: TestClient) -> None:
    seasons = get(client, "/api/v2/ipl/simulate/seasons")
    years = [s["season"] for s in seasons]
    assert years == sorted(years, reverse=True)
    final = next(s for s in seasons if s["season"] == 2019)
    assert {"MI", "CSK"} <= {t["team"]["franchise_id"] for t in final["teams"]}

    squad = get(client, "/api/v2/ipl/simulate/squad/2019/MI")
    assert squad["season"] == 2019
    assert squad["display_name"] == "Mumbai Indians"
    ids = [p["player_id"] for p in squad["players"]]
    assert len(ids) >= 11
    assert len(set(ids)) == len(ids)
    appearances = [p["matches"] for p in squad["players"]]
    assert appearances == sorted(appearances, reverse=True)
    assert min(appearances) >= 1
    assert len(squad["xi"]) == 11
    assert set(squad["xi"]) <= set(ids)
    assert len(squad["bowlers"]) >= 5
    assert set(squad["bowlers"]) <= set(squad["xi"])
    assert client.get("/api/v2/ipl/simulate/squad/2019/XYZ").status_code == 404
    assert client.get("/api/v2/ipl/simulate/squad/1990/MI").status_code == 404


def test_simulate_a_season(client: TestClient) -> None:
    mi = get(client, "/api/v2/ipl/simulate/squad/2019/MI")
    csk = get(client, "/api/v2/ipl/simulate/squad/2019/CSK")
    body = {
        "a": {"franchise_id": "MI", "batters": mi["xi"]},
        "b": {"franchise_id": "CSK", "batters": csk["xi"]},
        "season": 2019,
        "simulations": 1000,
    }
    result = post(client, "/api/v2/ipl/simulate/match", body)
    assert abs(result["a_win_pct"] + result["b_win_pct"] + result["tie_pct"] - 100) < 0.2
    # Every player must come from the side's squad that season.
    stranger = {**body, "b": {"franchise_id": "CSK", "batters": mi["xi"]}}
    response = client.post("/api/v2/ipl/simulate/match", json=stranger)
    assert response.status_code == 422
    assert "did not play for Chennai Super Kings in 2019" in response.json()["detail"]
    teamless = {**body, "a": {"batters": mi["xi"]}}
    assert client.post("/api/v2/ipl/simulate/match", json=teamless).status_code == 422
    absent = {**body, "season": 2008}
    assert client.post("/api/v2/ipl/simulate/match", json=absent).status_code in (404, 422)


def test_what_if_moves_the_model_estimate(client: TestClient) -> None:
    base = {"match_id": 1181768, "innings_no": 2, "seq_no": 100, "simulations": 1000}
    real = post(client, "/api/v2/ipl/simulate/state", base)
    assert real["label"] == "Model simulation"
    assert real["batting"]["franchise_id"] == "CSK"
    assert real["target"] == 150
    # No edit: the what-if is the model's own estimate.
    assert abs(real["whatif_win_pct"] - real["model_win_pct"]) < 0.11
    more = post(
        client, "/api/v2/ipl/simulate/state", {**base, "runs": real["actual"]["score"]["runs"] + 20}
    )
    assert more["whatif_win_pct"] > real["whatif_win_pct"]
    worse = post(client, "/api/v2/ipl/simulate/state", {**base, "wickets": 8})
    assert worse["edited"]["score"]["wickets"] == 8
    assert worse["whatif_win_pct"] < real["whatif_win_pct"]


def test_what_if_first_innings_and_errors(client: TestClient) -> None:
    start = post(
        client, "/api/v2/ipl/simulate/state", {"match_id": 1181768, "innings_no": 1, "seq_no": 0}
    )
    assert start["actual"]["score"] == {"runs": 0, "wickets": 0, "balls": 0}
    assert start["target"] is None
    assert 100 < start["actual"]["total"]["p50"] < 250
    missing = client.post(
        "/api/v2/ipl/simulate/state", json={"match_id": 1181768, "innings_no": 1, "seq_no": 9999}
    )
    assert missing.status_code == 404
    unknown = {"match_id": 1, "innings_no": 1, "seq_no": 0}
    assert client.post("/api/v2/ipl/simulate/state", json=unknown).status_code == 404


def test_unscored_data_has_no_simulator(client: TestClient, unscored_client: TestClient) -> None:
    # XIs need only the data; simulating needs the published models.
    assert unscored_client.get("/api/v2/ipl/simulate/xi/MI").status_code == 200
    body = _request(client)
    assert unscored_client.post("/api/v2/ipl/simulate/match", json=body).status_code == 503
    assert unscored_client.get("/api/v2/ipl/simulate/seasons").status_code == 503


def test_t20is_are_simulated_at_the_recent_scoring_level(client: TestClient) -> None:
    # The T20Is' simulator follows the recent scoring level (ADR-0013): scoring publishes
    # each match's era shift, and the API simulates with it.
    meta = get(client, "/api/v2/t20i/meta")
    assert meta["features"]["simulator"] is True
    # The 2016 World T20 final's sides (complete XIs in the fixtures).
    a, b, year = "ENG", "WI", 2016
    body = {
        "a": {
            "franchise_id": a,
            "batters": get(client, f"/api/v2/t20i/simulate/squad/{year}/{a}")["xi"],
        },
        "b": {
            "franchise_id": b,
            "batters": get(client, f"/api/v2/t20i/simulate/squad/{year}/{b}")["xi"],
        },
        "season": year,
        "simulations": 500,
    }
    result = post(client, "/api/v2/t20i/simulate/match", body)
    assert abs(result["a_win_pct"] + result["b_win_pct"] + result["tie_pct"] - 100) < 0.2
    assert result["simulator_version"] == "1.1.0"
