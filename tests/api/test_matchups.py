"""Matchup Lab endpoints and next-ball predictions over the fixture matches."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def _top_pair(client: TestClient) -> dict[str, Any]:
    body = client.get("/api/v1/matchups", params={"min_balls": 1, "page_size": 5}).json()
    assert body["items"], body
    pair: dict[str, Any] = body["items"][0]
    return pair


def _wicket(result: dict[str, Any]) -> float:
    return float(next(o for o in result["model"] if o["outcome"] == "out")["probability"])


def _ids(pair: dict[str, Any]) -> tuple[str, str]:
    return pair["batter"]["player_id"], pair["bowler"]["player_id"]


def test_list_sorts_by_balls_and_by_edge(client: TestClient) -> None:
    body = client.get("/api/v1/matchups", params={"min_balls": 1, "page_size": 50}).json()
    balls = [m["balls"] for m in body["items"]]
    assert balls == sorted(balls, reverse=True)
    assert body["kappa"] > 0
    for sort, reverse in (("batter_edge", True), ("bowler_edge", False)):
        edges = [
            m["edge"]
            for m in client.get(
                "/api/v1/matchups", params={"min_balls": 1, "sort": sort, "page_size": 50}
            ).json()["items"]
        ]
        assert edges == sorted(edges, reverse=reverse)


def test_list_filters_by_player(client: TestClient) -> None:
    batter, _ = _ids(_top_pair(client))
    body = client.get("/api/v1/matchups", params={"batter": batter, "min_balls": 1}).json()
    assert body["total"] >= 1
    assert all(m["batter"]["player_id"] == batter for m in body["items"])


def test_estimate_sits_between_the_record_and_the_expectation(client: TestClient) -> None:
    batter, bowler = _ids(_top_pair(client))
    detail = client.get(f"/api/v1/matchups/{batter}/{bowler}").json()
    h2h, sample = detail["head_to_head"], detail["sample"]
    assert h2h["balls"] == sum(r["balls"] for r in detail["by_phase"])
    assert h2h["dismissals"] == len(detail["dismissals"])
    assert sample["weight"] == pytest.approx(
        h2h["balls"] / (h2h["balls"] + sample["kappa"]), abs=1e-3
    )
    raw = detail["raw"]["strike_rate"]["value"]
    expected = detail["expected"]["strike_rate"]["value"]
    estimate = detail["estimate"]["strike_rate"]["value"]
    assert min(raw, expected) - 1 <= estimate <= max(raw, expected) + 1
    # Shrinkage narrows the interval far below the raw record's.
    estimate_sr, raw_sr = detail["estimate"]["strike_rate"], detail["raw"]["strike_rate"]
    assert estimate_sr["high"] - estimate_sr["low"] < raw_sr["high"] - raw_sr["low"]


def test_next_ball_odds_are_distributions(client: TestClient) -> None:
    batter, bowler = _ids(_top_pair(client))
    detail = client.get(f"/api/v1/matchups/{batter}/{bowler}").json()
    assert [b["phase"] for b in detail["next_ball"]] == ["powerplay", "middle", "death"]
    for ball in detail["next_ball"]:
        for side in ("model", "with_history"):
            assert sum(o["probability"] for o in ball[side]) == pytest.approx(1, abs=1e-3)
            assert [o["outcome"] for o in ball[side]] == [
                "dot",
                "one",
                "two",
                "three",
                "four",
                "six",
                "out",
            ]
    death, powerplay = detail["next_ball"][2], detail["next_ball"][0]
    assert death["expected_runs"] > powerplay["expected_runs"] * 0.9


def test_phase_filter_narrows_the_record(client: TestClient) -> None:
    batter, bowler = _ids(_top_pair(client))
    full = client.get(f"/api/v1/matchups/{batter}/{bowler}").json()
    for row in full["by_phase"]:
        part = client.get(
            f"/api/v1/matchups/{batter}/{bowler}", params={"phase": row["key"]}
        ).json()
        assert part["phase"] == row["key"]
        assert part["head_to_head"]["balls"] == row["balls"]
    assert (
        client.get(f"/api/v1/matchups/{batter}/{bowler}", params={"phase": "tea"}).status_code
        == 422
    )


def test_pairs_who_never_met(client: TestClient) -> None:
    batter, bowler = _ids(_top_pair(client))
    # A batter facing themself as a bowler: always a valid pair with no history.
    detail = client.get(f"/api/v1/matchups/{batter}/{batter}").json()
    assert detail["head_to_head"]["balls"] == 0
    assert detail["sample"]["level"] == "none"
    assert detail["raw"] is None
    assert detail["estimate"] is None
    for ball in detail["next_ball"]:
        assert ball["model"] == ball["with_history"]
    assert bowler


def test_unknown_players_are_404(client: TestClient) -> None:
    assert client.get("/api/v1/matchups/nobody/nobody").status_code == 404


def test_predict_next_ball(client: TestClient) -> None:
    batter, bowler = _ids(_top_pair(client))
    body = {"batter_id": batter, "bowler_id": bowler, "phase": "death", "innings": 2}
    response = client.post("/api/v1/predict/next-ball", json=body)
    assert response.status_code == 200
    result = response.json()
    assert sum(o["probability"] for o in result["model"]) == pytest.approx(1, abs=1e-3)
    assert result["history_balls"] > 0
    calm = client.post("/api/v1/predict/next-ball", json={**body, "pressure": "low"}).json()
    desperate = client.post(
        "/api/v1/predict/next-ball", json={**body, "pressure": "extreme"}
    ).json()
    assert _wicket(desperate) > _wicket(calm)
    assert client.post("/api/v1/predict/next-ball", json={**body, "wickets": 12}).status_code == 422
    assert (
        client.post("/api/v1/predict/next-ball", json={**body, "batter_id": "nobody"}).status_code
        == 404
    )


def test_matchups_need_the_scored_model(unscored_client: TestClient) -> None:
    assert unscored_client.get("/api/v1/matchups").status_code == 503
