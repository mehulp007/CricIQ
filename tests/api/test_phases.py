"""Phase Analysis: rates by phase, the over-by-over shape, results, toss, leaders, grounds."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from criciq_api.db import Database
from criciq_api.services.phases import (
    MIN_BALLS,
    PhaseDataMissingError,
    default_min_balls,
    get_phases,
)


def _get(client: TestClient, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture(scope="module")
def ipl(client: TestClient) -> dict[str, Any]:
    return _get(client, "/api/v2/ipl/phases")


@pytest.fixture(scope="module")
def serving(fixture_scored_serving_db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(fixture_scored_serving_db), read_only=True)


def test_the_three_t20_phases_cover_every_ball(
    ipl: dict[str, Any], serving: duckdb.DuckDBPyConnection
) -> None:
    assert ipl["format"] == "T20"
    assert [p["key"] for p in ipl["phases"]] == ["powerplay", "middle", "death"]
    assert [(p["first_over"], p["last_over"]) for p in ipl["phases"]] == [(1, 6), (7, 15), (16, 20)]
    runs = sum(p["runs"] for p in ipl["phases"])
    expected = serving.execute(
        "SELECT sum(runs_total) FROM deliveries d JOIN innings i USING (match_id, innings_no) "
        "WHERE NOT i.is_super_over"
    ).fetchone()
    assert expected is not None
    assert runs == expected[0]


def test_phase_rates_follow_the_shared_definitions(ipl: dict[str, Any]) -> None:
    for p in ipl["phases"]:
        if p["balls"]:
            assert p["run_rate"] == round(6 * p["runs"] / p["balls"], 2)
            assert p["dot_pct"] == round(100 * p["dots"] / p["balls"], 1)
            assert p["runs_per_innings"] == round(p["runs"] / p["innings"], 2)


def test_overs_add_up_to_the_phases(ipl: dict[str, Any]) -> None:
    assert ipl["over_block"] == 1
    overs = ipl["overs"]
    assert [o["first_over"] for o in overs] == sorted(o["first_over"] for o in overs)
    assert all(1 <= o["first_over"] <= 20 for o in overs)
    for phase in ipl["phases"]:
        inside = [o for o in overs if o["phase"] == phase["key"]]
        assert sum(o["runs"] for o in inside) == phase["runs"]
        assert sum(o["wickets"] for o in inside) == phase["wickets"]


def test_results_by_who_batted_first(ipl: dict[str, Any]) -> None:
    results = ipl["results"]
    first, chasing = results["batting_first"], results["chasing"]
    # Without a team, every decided match is won by one side or the other.
    assert first["matches"] == chasing["matches"] == results["matches"]
    assert first["won"] + chasing["won"] == results["matches"]
    assert results["first_innings_average"] is not None
    assert {t["decision"] for t in ipl["toss"]} <= {"bat", "field"}
    assert sum(t["matches"] for t in ipl["toss"]) <= results["matches"]


def test_leaders_are_ranked_with_ties(ipl: dict[str, Any]) -> None:
    assert [lead["phase"] for lead in ipl["leaders"]] == ["powerplay", "middle", "death"]
    for lead in ipl["leaders"]:
        runs = [b["runs"] for b in lead["batters"]]
        assert runs == sorted(runs, reverse=True)
        for a, b in zip(lead["batters"], lead["batters"][1:], strict=False):
            assert (b["rank"] == a["rank"]) == (a["runs"] == b["runs"])
        wickets = [b["wickets"] for b in lead["bowlers"]]
        assert wickets == sorted(wickets, reverse=True)
        for batter in lead["batters"]:
            assert batter["balls"] >= ipl["filters"]["min_balls"]


def test_small_data_takes_every_player(ipl: dict[str, Any]) -> None:
    assert ipl["filters"]["min_balls"] == 1
    assert default_min_balls("T20", 1000) == MIN_BALLS["T20"]
    assert default_min_balls("Test", 10) == 1


def test_grounds_list_their_phases_in_order(ipl: dict[str, Any]) -> None:
    assert ipl["grounds"]
    matches = [g["matches"] for g in ipl["grounds"]]
    assert matches == sorted(matches, reverse=True)
    for ground in ipl["grounds"]:
        keys = [p["phase"] for p in ground["phases"]]
        assert keys == sorted(keys, key=["powerplay", "middle", "death"].index)


def test_filters_narrow_the_figures(client: TestClient, ipl: dict[str, Any]) -> None:
    team = ipl["leaders"][0]["batters"][0]["team"]["franchise_id"]
    mine = _get(client, "/api/v2/ipl/phases", team=team)
    assert mine["filters"]["team"] == team
    assert sum(p["runs"] for p in mine["phases"]) < sum(p["runs"] for p in ipl["phases"])
    for lead in mine["leaders"]:
        for player in lead["batters"] + lead["bowlers"]:
            assert player["team"]["franchise_id"] == team
    first = _get(client, "/api/v2/ipl/phases", innings=1)
    assert sum(p["innings"] for p in first["phases"]) < sum(p["innings"] for p in ipl["phases"])
    venue = ipl["grounds"][0]["venue_id"]
    there = _get(client, "/api/v2/ipl/phases", venue=venue)
    assert [g["venue_id"] for g in there["grounds"]] == [venue]


def test_unknown_filters_give_empty_figures_not_errors(client: TestClient) -> None:
    body = _get(client, "/api/v2/ipl/phases", team="ZZZ", venue="nowhere", min_balls=500)
    assert all(p["innings"] == 0 and p["run_rate"] is None for p in body["phases"])
    assert body["overs"] == []
    assert body["results"]["matches"] == 0
    assert body["results"]["batting_first"]["win_pct"] is None
    assert all(not lead["batters"] and not lead["bowlers"] for lead in body["leaders"])


def test_bad_filters_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v2/ipl/phases", params={"innings": 3}).status_code == 422
    assert client.get("/api/v2/ipl/phases", params={"from": 2020, "to": 2010}).status_code == 422
    assert client.get("/api/v2/ipl/phases", params={"min_balls": 0}).status_code == 422


def test_tests_have_their_own_phases_and_ten_over_blocks(client: TestClient) -> None:
    body = _get(client, "/api/v2/test/phases")
    assert body["format"] == "Test"
    assert [p["key"] for p in body["phases"]] == ["new_ball", "middle", "second_new_ball"]
    assert body["phases"][-1]["last_over"] is None
    assert body["over_block"] == 10
    assert all((o["first_over"] - 1) % 10 == 0 for o in body["overs"])
    assert all(o["last_over"] <= 150 for o in body["overs"])
    assert body["results"]["average_total_defended"] is None
    assert _get(client, "/api/v2/test/phases", innings=4)["filters"]["innings"] == 4


def test_a_build_without_phase_tables_says_so(fixture_serving_db: Path, tmp_path: Path) -> None:
    older = tmp_path / "serving.duckdb"
    shutil.copyfile(fixture_serving_db, older)
    with duckdb.connect(str(older)) as con:
        con.execute("DROP TABLE phase_batting")
    with pytest.raises(PhaseDataMissingError, match="criciq-data extras"):
        get_phases(Database(older))
