"""/api/v2/test: Test cricket, with four innings, draws and the chase what-if (V2-6)."""

from typing import Any

from fastapi.testclient import TestClient

INNINGS_WIN = 1122310  # South Africa beat Zimbabwe by an innings and 120 runs (2017)
CHASE_WIN = 1223869  # Australia chase 90 at Adelaide after India's 36 all out (2020)
DRAW = 1223871  # Sydney 2021: India bat out the last day
TWO_RUNS = 215010  # Edgbaston 2005: England win by two runs


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_tests_are_served(client: TestClient) -> None:
    meta = get(client, "/api/v2/test/meta")
    assert meta["competition"]["format"] == "Test"
    assert meta["features"]["simulator"] is False


def test_results_say_how_a_test_ended(client: TestClient) -> None:
    page = get(client, "/api/v2/test/matches?page_size=10")
    results = {m["match_id"]: m for m in page["items"]}
    assert results[DRAW]["result_text"] == "Match drawn"
    assert results[DRAW]["outcome_type"] == "draw"
    innings = results[INNINGS_WIN]
    assert innings["result_text"] == "South Africa won by an innings and 120 runs"
    assert innings["won_by_innings"] is True
    # Every innings of each side, in order.
    edgbaston = results[TWO_RUNS]
    assert [i["runs"] for i in edgbaston["team_a"]["innings"]] == [407, 182]
    assert [i["runs"] for i in edgbaston["team_b"]["innings"]] == [308, 279]


def test_a_test_replays_with_three_outcomes(client: TestClient) -> None:
    timeline = get(client, f"/api/v2/test/matches/{TWO_RUNS}/timeline")
    assert [i["innings_no"] for i in timeline["innings"]] == [1, 2, 3, 4]
    assert all(i["max_balls"] is None for i in timeline["innings"])
    model = timeline["win_probability"]
    assert model["outcomes"] == 3
    assert model["factor_keys"] == []
    for d in timeline["deliveries"]:
        assert d["wp"] is not None
        assert d["wp_draw"] is not None
        assert 0 <= d["wp"] + d["wp_draw"] <= 1 + 1e-9
    # England batted first and won: the last ball carries the result.
    assert timeline["deliveries"][-1]["wp"] == 1.0
    # Every innings is projected.
    projected = {d["innings_no"] for d in timeline["deliveries"] if d["projection"]}
    assert projected == {1, 2, 3, 4}
    # Five days, estimated, in order.
    days = timeline["days"]
    assert [d["day"] for d in days] == [1, 2, 3, 4]
    assert days[0] == {"day": 1, "innings_no": 1, "seq_no": 0}


def test_a_draw_ends_drawn(client: TestClient) -> None:
    timeline = get(client, f"/api/v2/test/matches/{DRAW}/timeline")
    assert timeline["deliveries"][-1]["wp_draw"] == 1.0
    detail = get(client, f"/api/v2/test/matches/{INNINGS_WIN}")
    # Zimbabwe followed on.
    assert [i["follow_on"] for i in detail["innings"]] == [False, False, True]


def test_the_chase_what_if_moves_the_right_way(client: TestClient) -> None:
    base = f"/api/v2/test/matches/{TWO_RUNS}/chase?seq=200"
    real = get(client, base)
    assert real["batting_team"]["franchise_id"] == "AUS"
    assert real["real"] == real["edited"]
    first = real["real"]
    assert abs(first["won"] + first["drawn"] + first["lost"] - 1) < 1e-3
    easier = get(client, f"{base}&needed={max(first['runs_needed'] - 50, 1)}")
    assert easier["edited"]["won"] > first["won"]
    fewer = get(client, f"{base}&wickets={max(first['wickets_in_hand'] - 3, 1)}")
    assert fewer["edited"]["won"] < first["won"]
    # A limited-overs match has no chase what-if.
    assert client.get("/api/v2/ipl/matches/1181768/chase?seq=10").status_code == 404


def test_the_chase_calculator(client: TestClient) -> None:
    sides = get(client, "/api/v2/test/chase/sides")
    ids = [s["franchise_id"] for s in sides["sides"]]
    assert {"ENG", "AUS", "IND"} <= set(ids)
    base = "/api/v2/test/chase?batting=IND&fielding=AUS&wickets=10&overs=90"
    easy = get(client, f"{base}&needed=100")
    hard = get(client, f"{base}&needed=400")
    assert easy["outcome"]["won"] > hard["outcome"]["won"]
    assert len(easy["by_runs_needed"]) == 60
    for venue in ("home", "away", "neutral"):
        found = get(client, f"{base}&needed=250&venue={venue}")
        assert found["venue"] == venue
        o = found["outcome"]
        assert abs(o["won"] + o["drawn"] + o["lost"] - 1) < 1e-3
    assert (
        client.get(
            "/api/v2/test/chase?batting=IND&fielding=IND&needed=1&wickets=1&overs=1"
        ).status_code
        == 404
    )


def test_test_teams_count_draws(client: TestClient) -> None:
    teams = get(client, "/api/v2/test/teams")
    india = next(f for f in teams["franchises"] if f["franchise_id"] == "IND")
    record = india["record"]
    assert record["drawn"] == 1
    assert record["played"] == record["won"] + record["lost"] + record["drawn"]
