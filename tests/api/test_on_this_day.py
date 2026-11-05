"""On This Day: the matches on a calendar date, their standout figures and biggest swing."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from criciq_api.services.on_this_day import InvalidDateError, check_date

# The 2019 IPL final (12 May 2019) is in every build of the data, fixtures included.
FINAL = 1181768


def _get(client: TestClient, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_the_day_of_the_2019_final(client: TestClient) -> None:
    body = _get(client, "/api/v2/ipl/on-this-day", month=5, day=12)
    assert (body["month"], body["day"]) == (5, 12)
    final = next(e for e in body["entries"] if e["match_id"] == FINAL)
    assert final["year"] == 2019
    assert final["stage"] == "Final"
    assert final["is_playoff"] is True
    assert {t["franchise_id"] for t in final["teams"]} == {"MI", "CSK"}
    assert final["result"].startswith("Mumbai Indians won")
    assert final["notability"] >= 3
    assert final["batting"]["kind"] == "batting"
    assert final["bowling"]["figure"].count("/") == 1
    assert final["highlight"] in (final["batting"], final["bowling"])
    assert final["headline"].startswith(final["highlight"]["name"] + ": ")
    assert final["player_of_match"]
    # A scored database has the match's biggest swing, at a ball of the replay.
    assert final["swing"] is not None
    innings, seq = final["swing"]["ball"].split(".")
    assert int(innings) in (1, 2)
    assert int(seq) >= 0
    assert final["swing"]["after"] > final["swing"]["before"]


def test_entries_are_most_notable_first(client: TestClient) -> None:
    for month, day in ((5, 12), (4, 18), (6, 3)):
        entries = _get(client, "/api/v2/ipl/on-this-day", month=month, day=day)["entries"]
        keys = [(-e["notability"], e["date"]) for e in entries]
        assert [k[0] for k in keys] == sorted(k[0] for k in keys)


def test_a_day_without_matches_is_empty(client: TestClient) -> None:
    assert _get(client, "/api/v2/ipl/on-this-day", month=12, day=25)["entries"] == []


def test_every_competition_serves_it(client: TestClient) -> None:
    for competition in ("t20i", "odi", "test"):
        _get(client, f"/api/v2/{competition}/on-this-day", month=1, day=1)


def test_an_unscored_database_has_no_swings(unscored_client: TestClient) -> None:
    body = _get(unscored_client, "/api/v2/ipl/on-this-day", month=5, day=12)
    final = next(e for e in body["entries"] if e["match_id"] == FINAL)
    assert final["swing"] is None
    assert final["headline"]


def test_dates_are_checked(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/on-this-day", params={"month": 13, "day": 1}).status_code == 422
    assert client.get("/api/v2/ipl/on-this-day", params={"month": 2, "day": 30}).status_code == 422
    assert client.get("/api/v2/ipl/on-this-day", params={"month": 4, "day": 31}).status_code == 422
    assert client.get("/api/v2/ipl/on-this-day", params={"month": 2, "day": 29}).status_code == 200
    assert client.get("/api/v2/ipl/on-this-day").status_code == 422


@pytest.mark.parametrize(("month", "day"), [(2, 29), (12, 31), (1, 1)])
def test_real_dates(month: int, day: int) -> None:
    check_date(month, day)


@pytest.mark.parametrize(("month", "day"), [(0, 1), (2, 30), (11, 31), (6, 0)])
def test_impossible_dates(month: int, day: int) -> None:
    with pytest.raises(InvalidDateError):
        check_date(month, day)
