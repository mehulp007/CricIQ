"""/api/v2/odi: an ODI is replayed, explained and simulated over 50 overs (ADR-0012)."""

from typing import Any

from fastapi.testclient import TestClient

WORLD_CUP_FINAL = 1144530  # 2019: tied, then a tied super over, won on boundaries
RAIN_CHASE = 224227  # 2005, New Zealand v South Africa, a D/L chase


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_an_odi_replays_over_fifty_overs_with_its_own_model(client: TestClient) -> None:
    timeline = get(client, f"/api/v2/odi/matches/{WORLD_CUP_FINAL}/timeline")
    regulation = [i for i in timeline["innings"] if not i["is_super_over"]]
    assert [i["max_balls"] for i in regulation] == [300, 300]
    first = [d for d in timeline["deliveries"] if d["innings_no"] == 1]
    assert first[-1]["team_runs"] == 241
    assert first[-1]["legal_ball_no"] == 300
    model = timeline["win_probability"]
    assert model["version"] == "1.0.0"
    assert model["trained_from"] == 2002
    # Level after regulation play; the super overs are not modelled.
    chase = [d for d in timeline["deliveries"] if d["innings_no"] == 2]
    assert chase[-1]["wp"] == 0.5
    summary = timeline["summary"]
    assert (
        summary["result_text"] == "Match tied (England won on boundaries after a tied super over)"
    )


def test_a_rain_revised_chase_is_replayed_over_its_revised_overs(client: TestClient) -> None:
    timeline = get(client, f"/api/v2/odi/matches/{RAIN_CHASE}/timeline")
    chase = timeline["innings"][1]
    assert chase["target_balls"] is not None
    assert chase["target_balls"] < 300
    assert chase["max_balls"] == chase["target_balls"]


def test_odis_have_a_simulator(client: TestClient) -> None:
    meta = get(client, "/api/v2/odi/meta")
    assert meta["competition"]["format"] == "ODI"
    assert meta["features"]["simulator"] is True
    england = get(client, "/api/v2/odi/simulate/squad/2019/ENG")
    new_zealand = get(client, "/api/v2/odi/simulate/squad/2019/NZ")
    body = {
        "a": {"franchise_id": "ENG", "batters": england["xi"]},
        "b": {"franchise_id": "NZ", "batters": new_zealand["xi"]},
        "season": 2019,
        "simulations": 500,
    }
    result = post(client, "/api/v2/odi/simulate/match", body)
    assert abs(result["a_win_pct"] + result["b_win_pct"] + result["tie_pct"] - 100) < 0.2
    # Fifty-over totals, not twenty-over ones.
    firsts = [side["first_innings"] for side in result["sides"] if side["first_innings"]]
    assert firsts
    assert all(first["p50"] > 150 for first in firsts)


def test_the_what_if_plays_the_rest_of_an_odi(client: TestClient) -> None:
    base = {"match_id": WORLD_CUP_FINAL, "innings_no": 2, "seq_no": 200, "simulations": 500}
    real = post(client, "/api/v2/odi/simulate/state", base)
    assert real["target"] == 242
    more = post(
        client, "/api/v2/odi/simulate/state", {**base, "runs": real["actual"]["score"]["runs"] + 30}
    )
    assert more["whatif_win_pct"] > real["whatif_win_pct"]
