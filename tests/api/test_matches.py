from typing import Any

import pytest
from fastapi.testclient import TestClient


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- list


def test_list_is_paginated_newest_first(client: TestClient) -> None:
    page = get(client, "/api/v2/ipl/matches", page_size=5)
    assert page["total"] == 14
    assert len(page["items"]) == 5
    dates = [m["date"] for m in page["items"]]
    assert dates == sorted(dates, reverse=True)

    oldest = get(client, "/api/v2/ipl/matches", sort="oldest", page_size=1)["items"][0]
    assert oldest["match_id"] == 335982


def test_list_filters(client: TestClient) -> None:
    assert get(client, "/api/v2/ipl/matches", season=2008)["total"] == 2
    mi = get(client, "/api/v2/ipl/matches", team="MI")["items"]
    assert mi
    assert all("MI" in (m["team_a"]["franchise_id"], m["team_b"]["franchise_id"]) for m in mi)
    finals = get(client, "/api/v2/ipl/matches", playoffs="true")["items"]
    assert finals
    assert all(m["is_playoff"] for m in finals)
    assert get(client, "/api/v2/ipl/matches", venue="nowhere")["total"] == 0


def test_list_rejects_bad_parameters(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/matches", params={"page_size": 1000}).status_code == 422
    assert client.get("/api/v2/ipl/matches", params={"sort": "random"}).status_code == 422


@pytest.mark.parametrize(
    ("match_id", "team_a", "score_a", "team_b", "score_b", "result"),
    [
        (
            335982,
            "KKR",
            (222, 3, "20.0"),
            "RCB",
            (82, 10, "15.1"),
            "Kolkata Knight Riders won by 140 runs",
        ),
        (1181768, "MI", (149, 8, "20.0"), "CSK", (148, 7, "20.0"), "Mumbai Indians won by 1 run"),
        (
            1370353,
            "GT",
            (214, 4, "20.0"),
            "CSK",
            (171, 5, "15.0"),
            "Chennai Super Kings won by 5 wickets (D/L)",
        ),
        (
            1082625,
            "GL",
            (153, 9, "20.0"),
            "MI",
            (153, 10, "20.0"),
            "Match tied (Mumbai Indians won the super over)",
        ),
        (1359519, "LSG", (125, 7, "19.2"), "CSK", (None, None, None), "No result"),
    ],
)
def test_summaries_read_like_scorecards(
    client: TestClient,
    match_id: int,
    team_a: str,
    score_a: tuple[int | None, int | None, str | None],
    team_b: str,
    score_b: tuple[int | None, int | None, str | None],
    result: str,
) -> None:
    summary = get(client, f"/api/v2/ipl/matches/{match_id}")["summary"]
    a, b = summary["team_a"], summary["team_b"]
    assert (a["franchise_id"], (a["runs"], a["wickets"], a["overs"])) == (team_a, score_a)
    assert (b["franchise_id"], (b["runs"], b["wickets"], b["overs"])) == (team_b, score_b)
    assert summary["result_text"] == result


# --------------------------------------------------------------------------- scorecard


def test_2019_final_scorecard(client: TestClient) -> None:
    detail = get(client, "/api/v2/ipl/matches/1181768")
    assert detail["summary"]["player_of_match"] == ["Jasprit Bumrah"]
    chase = detail["innings"][1]
    batting = {b["name"]: b for b in chase["batting"]}
    assert (batting["SR Watson"]["runs"], batting["SR Watson"]["balls"]) == (80, 59)
    assert batting["SR Watson"]["dismissal"].startswith("run out")
    assert batting["F du Plessis"]["dismissal"] == "st Q de Kock b KH Pandya"
    assert batting["RA Jadeja"]["is_out"] is False
    assert [p["name"] for p in chase["did_not_bat"]] == [
        "DL Chahar",
        "Harbhajan Singh",
        "Imran Tahir",
    ]

    chahar = next(b for b in detail["innings"][0]["bowling"] if b["name"] == "DL Chahar")
    assert (chahar["overs"], chahar["maidens"], chahar["runs"], chahar["wickets"]) == (
        "4.0",
        1,
        26,
        3,
    )

    fall = chase["fall_of_wickets"]
    assert [f["wicket"] for f in fall] == list(range(1, 8))
    assert (fall[-1]["runs"], fall[-1]["overs"]) == (148, "20.0")


def test_scorecard_totals_are_consistent(client: TestClient) -> None:
    for match in get(client, "/api/v2/ipl/matches", page_size=100)["items"]:
        for innings in get(client, f"/api/v2/ipl/matches/{match['match_id']}")["innings"]:
            batting_runs = sum(b["runs"] for b in innings["batting"])
            assert batting_runs + innings["extras"]["total"] == innings["runs"]
            bowled = sum(
                int(b["overs"].split(".")[0]) * 6 + int(b["overs"].split(".")[1])
                for b in innings["bowling"]
            )
            overs = innings["overs"].split(".")
            assert bowled == int(overs[0]) * 6 + int(overs[1])


def test_unknown_match_is_404(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/matches/1").status_code == 404
    assert client.get("/api/v2/ipl/matches/1/timeline").status_code == 404


# --------------------------------------------------------------------------- timeline


def test_timeline_replays_to_the_final_score(client: TestClient) -> None:
    timeline = get(client, "/api/v2/ipl/matches/335982/timeline")
    deliveries = timeline["deliveries"]
    first = [d for d in deliveries if d["innings_no"] == 1]
    assert sum(d["runs_total"] for d in first) == first[-1]["team_runs"] == 222
    assert first[-1]["legal_ball_no"] == 120

    referenced = {d["batter_id"] for d in deliveries} | {d["bowler_id"] for d in deliveries}
    assert referenced <= set(timeline["players"])
    assert set(timeline["teams"]) == {i["batting_team_id"] for i in timeline["innings"]}

    chase = timeline["innings"][1]
    assert (chase["target_runs"], chase["target_balls"], chase["max_balls"]) == (223, 120, 120)


def test_timeline_marks_super_overs_and_substitutions(client: TestClient) -> None:
    tie = get(client, "/api/v2/ipl/matches/1216517/timeline")
    assert [i["is_super_over"] for i in tie["innings"]] == [False, False, True, True, True, True]
    assert all(i["max_balls"] == 6 for i in tie["innings"] if i["is_super_over"])

    final = get(client, "/api/v2/ipl/matches/1473511/timeline")
    reasons = {s["reason"] for s in final["substitutions"]}
    assert reasons == {"impact_player"}


def test_responses_are_cacheable_and_compressed(client: TestClient) -> None:
    response = client.get(
        "/api/v2/ipl/matches/1181768/timeline", headers={"Accept-Encoding": "gzip"}
    )
    assert "s-maxage" in response.headers["Cache-Control"]
    assert response.headers["Content-Encoding"] == "gzip"


# --------------------------------------------------------------------------- win probability


def test_timeline_carries_win_probability(client: TestClient) -> None:
    timeline = get(client, "/api/v2/ipl/matches/1181768/timeline")
    model = timeline["win_probability"]
    assert model["factor_keys"] == ["situation", "wickets", "recent"]
    assert model["trained_from"] == 2008

    innings = timeline["innings"]
    assert all(0 < i["wp_start"] < 1 for i in innings)
    assert all(len(i["factors_start"]) == 3 for i in innings)

    deliveries = timeline["deliveries"]
    assert all(0 <= d["wp"] <= 1 for d in deliveries)
    # Mumbai batted first and won by a run off the last ball: the rules say 100%.
    assert deliveries[-1]["wp"] == 1.0
    assert deliveries[-1]["factors"] is None
    assert all(len(d["factors"]) == 3 for d in deliveries[:-1])


def test_ties_end_level_and_super_overs_are_not_modelled(client: TestClient) -> None:
    timeline = get(client, "/api/v2/ipl/matches/1216517/timeline")
    regulation = [d for d in timeline["deliveries"] if d["innings_no"] <= 2]
    super_overs = [d for d in timeline["deliveries"] if d["innings_no"] > 2]
    assert regulation[-1]["wp"] == 0.5
    assert super_overs
    assert all(d["wp"] is None for d in super_overs)


def test_timeline_without_model_scores_still_replays(unscored_client: TestClient) -> None:
    timeline = get(unscored_client, "/api/v2/ipl/matches/1181768/timeline")
    assert timeline["win_probability"] is None
    assert all(d["wp"] is None for d in timeline["deliveries"])
    assert all(i["wp_start"] is None for i in timeline["innings"])
    assert all(d["pressure"] is None and d["momentum"] is None for d in timeline["deliveries"])


def test_timeline_carries_pressure_and_momentum(client: TestClient) -> None:
    """The 2019 final: CSK needed two off the last ball."""
    timeline = get(client, "/api/v2/ipl/matches/1181768/timeline")
    bands = timeline["win_probability"]["pressure_thresholds"]
    assert bands == sorted(bands)
    assert len(bands) == 3
    chase = [d for d in timeline["deliveries"] if d["innings_no"] == 2]
    *_, before_last, last = chase
    assert last["pressure"] is None  # the match is over
    assert before_last["pressure"] >= 95
    assert before_last["leverage"] > 5
    assert last["momentum"] < 0  # CSK lost it on the last ball
    first = timeline["innings"][0]
    assert 0 <= first["pressure_start"] <= 100
    for d in timeline["deliveries"]:
        if d["innings_no"] <= 2 and d["pressure"] is not None:
            assert 0 <= d["pressure"] <= 100
            assert d["leverage"] >= 0


def test_first_innings_carries_score_projections(client: TestClient) -> None:
    timeline = get(client, "/api/v2/ipl/matches/1181768/timeline")
    model = timeline["score_projection"]
    assert model["levels"] == [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
    first = [d for d in timeline["deliveries"] if d["innings_no"] == 1]
    chase = [d for d in timeline["deliveries"] if d["innings_no"] == 2]
    assert len(timeline["innings"][0]["projection_start"]) == 7
    assert timeline["innings"][1]["projection_start"] is None
    for d in first[:-1]:
        q = d["projection"]
        assert q == sorted(q)
        assert q[0] >= d["team_runs"]
    assert first[-1]["projection"] is None  # the innings is over: the total is known
    assert all(d["projection"] is None for d in chase)
