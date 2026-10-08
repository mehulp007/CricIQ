"""/api/v2/{competition}/series: series and tournaments of the international competitions."""

from typing import Any

from fastapi.testclient import TestClient

INDIA_IN_AUSTRALIA = "2020-21-india-tour-of-australia"
EDGBASTON = "2005-australia-tour-of-england-and-scotland"
WORLD_CUP_2019 = "2019-mens-cricket-world-cup"
DASH = "\u2013"


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_series_are_listed_newest_first(client: TestClient) -> None:
    page = get(client, "/api/v2/test/series")
    ids = [s["event_id"] for s in page["items"]]
    assert ids[0] == INDIA_IN_AUSTRALIA
    assert EDGBASTON in ids
    assert page["total"] == len(ids)
    assert page["years"][0] == 2021
    first = page["items"][0]
    assert first["season"] == "2020/21"
    assert first["kind"] == "series"
    # Long before the fixtures' data date: over.
    assert first["recent"] is False
    # The fixtures hold the first and third Tests: the numbering shows one missing.
    assert first["missing"] == 1
    assert first["result_text"] == f"Australia won 1{DASH}0, 1 drawn, 1 not in the data"
    assert [t["franchise_id"] for t in first["teams"]] == ["AUS", "IND"]


def test_filters(client: TestClient) -> None:
    by_year = get(client, "/api/v2/test/series?year=2005")
    assert [s["event_id"] for s in by_year["items"]] == [EDGBASTON]
    by_team = get(client, "/api/v2/test/series?team=zim")
    assert all("ZIM" in [t["franchise_id"] for t in s["teams"]] for s in by_team["items"])
    assert get(client, "/api/v2/test/series?kind=tournament")["total"] == 0


def test_a_one_match_series_reads_as_its_match(client: TestClient) -> None:
    detail = get(client, f"/api/v2/test/series/{EDGBASTON}")
    assert detail["summary"]["result_text"] == "England won by 2 runs"
    assert [m["summary"]["match_id"] for m in detail["matches"]] == [215010]
    assert detail["rounds"] == []
    assert detail["batters"][0]["runs"] >= detail["batters"][-1]["runs"]
    assert detail["bowlers"][0]["wickets"] >= 1
    # Expected result added, both ways.
    assert detail["decisive"]
    # England came back to win from behind.
    assert 0 < detail["matches"][0]["winner_low"] < 0.5


def test_a_major_tournament_names_its_champion(client: TestClient) -> None:
    majors = get(client, "/api/v2/odi/series?major=true")
    final = next(s for s in majors["items"] if s["event_id"] == WORLD_CUP_2019)
    assert final["tournament_id"] == "cricket-world-cup"
    assert final["champion"]["franchise_id"] == "ENG"
    assert final["runner_up"]["franchise_id"] == "NZ"
    assert final["result_text"] == "England beat New Zealand in the final"
    assert all(s["tournament_id"] for s in majors["items"])


def test_a_match_knows_its_series(client: TestClient) -> None:
    detail = get(client, "/api/v2/test/matches/1223869")
    assert detail["series"]["event_id"] == INDIA_IN_AUSTRALIA
    timeline = get(client, "/api/v2/test/matches/1223869/timeline")
    assert timeline["series"]["name"] == "India tour of Australia"
    # The IPL keeps no series.
    assert get(client, "/api/v2/ipl/matches/1181768")["series"] is None


def test_two_sides_series(client: TestClient) -> None:
    record = get(client, "/api/v2/test/series/h2h?a=IND&b=AUS")
    assert [s["event_id"] for s in record["series"]] == [INDIA_IN_AUSTRALIA]
    # A series of two or more matches counts.
    assert (record["played"], record["a_won"], record["b_won"]) == (1, 0, 1)
    assert client.get("/api/v2/test/series/h2h?a=IND&b=IND").status_code == 422


def test_series_are_international_only(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/series").status_code == 404
    assert client.get("/api/v2/test/series/no-such-series").status_code == 404


def test_careers_count_hundreds_and_best_figures(client: TestClient) -> None:
    careers = get(client, "/api/v2/players/ba607b88")
    lines = {c["competition"]: c for c in careers["careers"]}
    for line in lines.values():
        assert line["hundreds"] >= 0
        assert line["fifties"] >= 0
        assert line["innings"] >= (1 if line["runs"] else 0)
        if line["runs"]:
            assert line["high"] is not None
    ratings = get(client, "/api/v2/players/ba607b88/ratings")
    assert ratings["player_id"] == "ba607b88"
    for line in ratings["lines"]:
        assert {r["key"] for r in line["batting"]} <= {"scoring", "survival", "impact"}
    assert client.get("/api/v2/players/nobody00/ratings").status_code == 404
