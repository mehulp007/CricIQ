"""Chart Studio: every measure against a direct query, groupings, splits, filters and bad specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from criciq_api.db import Database, QueryTimeoutError
from criciq_api.repositories.studio import DATASETS, MAX_SERIES
from criciq_api.services.studio import _figure


def _run(client: TestClient, competition: str = "ipl", **spec: Any) -> dict[str, Any]:
    response = client.post(f"/api/v2/{competition}/studio/query", json=spec)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture(scope="module")
def serving(fixture_scored_serving_db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(fixture_scored_serving_db), read_only=True)


def _one(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> Any:
    found = con.execute(sql, params or []).fetchone()
    assert found is not None
    return found[0]


def _top_batter(con: duckdb.DuckDBPyConnection) -> str:
    return str(
        _one(
            con,
            "SELECT player_id FROM player_batting_innings GROUP BY 1 "
            "ORDER BY sum(runs) DESC, player_id LIMIT 1",
        )
    )


def _top_bowler(con: duckdb.DuckDBPyConnection) -> str:
    return str(
        _one(
            con,
            "SELECT player_id FROM player_bowling_innings GROUP BY 1 "
            "ORDER BY sum(wickets) DESC, player_id LIMIT 1",
        )
    )


def test_options_list_every_dataset_with_its_measures(client: TestClient) -> None:
    response = client.get("/api/v2/ipl/studio/options")
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "T20"
    assert [d["key"] for d in body["datasets"]] == list(DATASETS)
    teams = next(d for d in body["datasets"] if d["key"] == "teams")
    assert "drawn" not in {m["key"] for m in teams["measures"]}  # Tests only
    assert body["teams"]
    assert body["seasons"]
    assert body["grounds"]
    assert [p["value"] for p in body["phases"]] == ["powerplay", "middle", "death"]
    assert body["max_series"] == MAX_SERIES

    test = client.get("/api/v2/test/studio/options").json()
    teams = next(d for d in test["datasets"] if d["key"] == "teams")
    keys = {m["key"] for m in teams["measures"]}
    assert "drawn" in keys
    assert "average_for" not in keys


BATTING = {
    "innings": "count(*)",
    "runs": "sum(runs)",
    "balls": "sum(balls)",
    "not_outs": "count(*) FILTER (WHERE NOT is_out)",
    "average": "round(sum(runs) / nullif(count(*) FILTER (WHERE is_out), 0), 2)",
    "strike_rate": "round(100 * sum(runs) / nullif(sum(balls), 0), 2)",
    "hundreds": "count(*) FILTER (WHERE runs >= 100)",
    "fifties": "count(*) FILTER (WHERE runs BETWEEN 50 AND 99)",
    "ducks": "count(*) FILTER (WHERE runs = 0 AND is_out)",
    "fours": "sum(fours)",
    "sixes": "sum(sixes)",
    "dot_pct": "round(100 * sum(dots) / nullif(sum(balls), 0), 1)",
    "boundary_pct": "round(100 * sum(fours + sixes) / nullif(sum(balls), 0), 1)",
    "runs_above_par": "round(sum(runs - par_runs), 1)",
}


def test_every_batting_measure_equals_a_direct_query(
    client: TestClient, serving: duckdb.DuckDBPyConnection
) -> None:
    player = _top_batter(serving)
    for start in range(0, len(BATTING), 6):
        keys = list(BATTING)[start : start + 6]
        body = _run(client, dataset="batting", measures=keys, filters={"players": [player]})
        [row] = body["rows"]
        assert row["group"]["player_id"] == player
        for key in keys:
            expected = _one(
                serving,
                f"SELECT {BATTING[key]} FROM player_batting_innings WHERE player_id = ?",
                [player],
            )
            assert row["values"][key] == pytest.approx(expected), key

    highest = _run(client, dataset="batting", measures=["highest"], filters={"players": [player]})[
        "rows"
    ][0]
    runs, out = serving.execute(
        "SELECT runs, is_out FROM player_batting_innings WHERE player_id = ? "
        "ORDER BY runs DESC, is_out LIMIT 1",
        [player],
    ).fetchall()[0]
    assert highest["values"]["highest"] == runs
    assert highest["display"]["highest"] == f"{runs}{'' if out else '*'}"


BOWLING = {
    "innings": "count(*)",
    "wickets": "sum(wickets)",
    "runs": "sum(runs)",
    "average": "round(sum(runs) / nullif(sum(wickets), 0), 2)",
    "economy": "round(6 * sum(runs) / nullif(sum(balls), 0), 2)",
    "strike_rate": "round(sum(balls) / nullif(sum(wickets), 0), 2)",
    "maidens": "sum(maidens)",
    "four_wickets": "count(*) FILTER (WHERE wickets = 4)",
    "five_wickets": "count(*) FILTER (WHERE wickets >= 5)",
    "dot_pct": "round(100 * sum(dots) / nullif(sum(balls), 0), 1)",
    "boundary_pct": "round(100 * sum(fours + sixes) / nullif(sum(balls), 0), 1)",
    "runs_saved": "round(sum(par_runs - runs), 1)",
}


def test_every_bowling_measure_equals_a_direct_query(
    client: TestClient, serving: duckdb.DuckDBPyConnection
) -> None:
    player = _top_bowler(serving)
    for start in range(0, len(BOWLING), 6):
        keys = list(BOWLING)[start : start + 6]
        [row] = _run(client, dataset="bowling", measures=keys, filters={"players": [player]})[
            "rows"
        ]
        for key in keys:
            expected = _one(
                serving,
                f"SELECT {BOWLING[key]} FROM player_bowling_innings WHERE player_id = ?",
                [player],
            )
            assert row["values"][key] == pytest.approx(expected), key

    [row] = _run(
        client, dataset="bowling", measures=["best", "overs"], filters={"players": [player]}
    )["rows"]
    wickets, runs = serving.execute(
        "SELECT wickets, runs FROM player_bowling_innings WHERE player_id = ? "
        "ORDER BY wickets DESC, runs LIMIT 1",
        [player],
    ).fetchall()[0]
    assert row["display"]["best"] == f"{wickets}/{runs}"
    balls = _one(
        serving, "SELECT sum(balls) FROM player_bowling_innings WHERE player_id = ?", [player]
    )
    assert row["display"]["overs"] == (
        f"{balls // 6}.{balls % 6}" if balls % 6 else f"{balls // 6}"
    )


def test_phase_and_career_measures(client: TestClient, serving: duckdb.DuckDBPyConnection) -> None:
    rows = _run(client, dataset="phase_batting", measures=["runs", "balls"], group_by="phase")[
        "rows"
    ]
    assert [r["group"]["key"] for r in rows] == ["powerplay", "middle", "death"]
    assert sum(r["values"]["runs"] for r in rows) == _one(
        serving, "SELECT sum(runs) FROM phase_batting"
    )

    player = _top_batter(serving)
    [row] = _run(
        client,
        dataset="careers",
        measures=["matches", "runs", "wickets", "catches", "stumpings", "wpa"],
        filters={"players": [player]},
    )["rows"]
    assert row["values"]["matches"] == _one(
        serving, "SELECT count(*) FROM match_players WHERE player_id = ?", [player]
    )
    assert row["values"]["runs"] == _one(
        serving, "SELECT sum(runs) FROM player_batting_innings WHERE player_id = ?", [player]
    )
    assert row["values"]["catches"] == _one(
        serving,
        "SELECT coalesce(sum(catches), 0) FROM player_fielding WHERE player_id = ?",
        [player],
    )
    assert row["values"]["wpa"] == pytest.approx(
        round(_one(serving, "SELECT sum(wpa) FROM player_wpa WHERE player_id = ?", [player]), 3)
    )
    assert next(
        c
        for c in _run(client, dataset="careers", measures=["wpa"], filters={"players": [player]})[
            "columns"
        ]
    )["model"]


def test_team_results(client: TestClient, serving: duckdb.DuckDBPyConnection) -> None:
    body = _run(
        client, dataset="teams", measures=["matches", "won", "lost", "win_pct"], group_by="team"
    )
    for row in body["rows"]:
        team = row["group"]["key"]
        won, lost, played = serving.execute(
            "SELECT count(*) FILTER (WHERE result = 'won'),"
            " count(*) FILTER (WHERE result = 'lost'),"
            " count(*) FILTER (WHERE result <> 'no_result')"
            " FROM team_matches WHERE franchise_id = ?",
            [team],
        ).fetchall()[0]
        assert (row["values"]["won"], row["values"]["lost"]) == (won, lost)
        assert row["values"]["win_pct"] == (round(100 * won / played, 1) if played else None)
        assert row["group"]["color"]


def test_rows_are_ranked_with_shared_ranks(client: TestClient) -> None:
    body = _run(client, dataset="batting", measures=["sixes"], limit=50)
    values = [r["values"]["sixes"] for r in body["rows"]]
    assert values == sorted(values, reverse=True)
    for prev, cur in zip(body["rows"], body["rows"][1:], strict=False):
        if cur["values"]["sixes"] == prev["values"]["sixes"]:
            assert cur["rank"] == prev["rank"]
            assert cur["tied"]
            assert prev["tied"]
        else:
            assert cur["rank"] > prev["rank"]
    assert body["spec"]["sort"] == "sixes"
    assert body["spec"]["order"] == "desc"
    # A bowler's economy ranks lowest first.
    economy = _run(client, dataset="bowling", measures=["economy"], min_sample=24)
    assert economy["spec"]["order"] == "asc"
    figures = [r["values"]["economy"] for r in economy["rows"]]
    assert figures == sorted(figures)
    assert all(r["sample"] >= 24 for r in economy["rows"])


def test_natural_groupings_keep_their_order(client: TestClient) -> None:
    seasons = _run(client, dataset="batting", measures=["runs"], group_by="season")
    keys = [int(r["group"]["key"]) for r in seasons["rows"]]
    assert keys == sorted(keys)
    assert seasons["spec"]["sort"] == "group"
    assert all(r["rank"] is None for r in seasons["rows"])
    positions = _run(client, dataset="batting", measures=["runs"], group_by="position")
    assert positions["rows"][0]["group"]["label"] == "No. 1"
    latest = _run(client, dataset="batting", measures=["runs"], group_by="season", order="desc")
    assert [int(r["group"]["key"]) for r in latest["rows"]] == sorted(keys, reverse=True)


def test_a_split_gives_series_and_cells(
    client: TestClient, serving: duckdb.DuckDBPyConnection
) -> None:
    players = [
        str(p)
        for (p,) in serving.execute(
            "SELECT player_id FROM player_batting_innings GROUP BY 1 "
            "ORDER BY sum(runs) DESC, player_id LIMIT 3"
        ).fetchall()
    ]
    body = _run(
        client,
        dataset="batting",
        measures=["runs", "strike_rate"],
        group_by="season",
        split_by="player",
        filters={"players": players},
    )
    assert {s["group"]["key"] for s in body["series"]} == set(players)
    for cell in body["cells"]:
        expected = _one(
            serving,
            "SELECT sum(runs) FROM player_batting_innings WHERE season = ? AND player_id = ?",
            [int(cell["group"]), cell["split"]],
        )
        assert cell["values"]["runs"] == expected
    # Each season's row is the total over the chosen players; each series the player's.
    for row in body["rows"]:
        in_season = [c for c in body["cells"] if c["group"] == row["group"]["key"]]
        assert row["values"]["runs"] == sum(c["values"]["runs"] for c in in_season)
    many = _run(client, dataset="batting", measures=["runs"], group_by="season", split_by="player")
    assert len(many["series"]) == MAX_SERIES
    few = _run(
        client,
        dataset="batting",
        measures=["runs"],
        group_by="season",
        split_by="player",
        series=3,
    )
    assert len(few["series"]) == 3
    assert {c["split"] for c in few["cells"]} <= {s["group"]["key"] for s in few["series"]}


def test_filters_narrow_the_figures(client: TestClient, serving: duckdb.DuckDBPyConnection) -> None:
    team = str(_one(serving, "SELECT team_id FROM player_batting_innings GROUP BY 1 ORDER BY 1"))
    season = int(_one(serving, "SELECT min(season) FROM player_batting_innings"))
    [row] = _run(
        client,
        dataset="batting",
        measures=["runs"],
        group_by=None,
        filters={"team": team, "season_from": season, "season_to": season},
    )["rows"]
    assert row["values"]["runs"] == _one(
        serving,
        "SELECT sum(runs) FROM player_batting_innings WHERE team_id = ? AND season = ?",
        [team, season],
    )
    assert row["group"] is None
    assert row["rank"] is None
    death = _run(
        client,
        dataset="phase_bowling",
        measures=["wickets"],
        group_by=None,
        filters={"phase": "death"},
    )["rows"][0]
    assert death["values"]["wickets"] == _one(
        serving, "SELECT sum(wickets) FROM phase_bowling WHERE phase = 'death'"
    )
    nobody = _run(client, dataset="batting", measures=["runs"], filters={"team": "NOPE"})
    assert nobody["rows"] == []


def test_the_query_is_shown_with_its_values(client: TestClient) -> None:
    body = _run(client, dataset="batting", measures=["runs"], filters={"team": "MI"}, limit=7)
    assert "player_batting_innings" in body["sql"]
    assert "?" in body["sql"]
    assert "'MI'" not in body["sql"]  # values travel as parameters
    assert "MI" in body["params"]
    assert 8 in body["params"]


def test_injection_attempts_are_refused(client: TestClient) -> None:
    for spec in (
        {"dataset": "batting", "measures": ["runs"], "filters": {"team": "MI'; DROP TABLE x--"}},
        {"dataset": "batting", "measures": ["runs"], "filters": {"players": ["a' OR '1'='1"]}},
        {"dataset": "batting", "measures": ["runs); DROP TABLE x;--"]},
        {"dataset": "batting", "measures": ["runs"], "sort": "runs DESC; --"},
        {"dataset": "matches", "measures": ["runs"]},
        {"dataset": "batting", "measures": ["runs"], "sql": "SELECT 1"},
    ):
        response = client.post("/api/v2/ipl/studio/query", json=spec)
        assert response.status_code == 422, spec


@pytest.mark.parametrize(
    "spec",
    [
        {"dataset": "teams", "measures": ["runs"]},
        {"dataset": "bowling", "measures": ["highest"]},
        {"dataset": "batting", "measures": ["runs", "runs"]},
        {"dataset": "batting", "measures": ["runs"], "group_by": "phase"},
        {"dataset": "batting", "measures": ["runs"], "split_by": "season", "group_by": None},
        {"dataset": "batting", "measures": ["runs"], "group_by": "season", "split_by": "season"},
        {"dataset": "careers", "measures": ["runs"], "group_by": "season"},
        {"dataset": "bowling", "measures": ["wickets"], "filters": {"position": 3}},
        {"dataset": "teams", "measures": ["won"], "filters": {"players": ["x"]}},
        {"dataset": "batting", "measures": ["runs"], "filters": {"phase": "death"}},
        {"dataset": "phase_batting", "measures": ["runs"], "filters": {"phase": "second_new"}},
        {"dataset": "batting", "measures": ["runs"], "sort": "average"},
        {"dataset": "batting", "measures": ["runs"], "sort": "group"},
        {
            "dataset": "batting",
            "measures": ["runs"],
            "filters": {"season_from": 2020, "season_to": 2010},
        },
        {"dataset": "teams", "measures": ["won"], "filters": {"innings": 3}},
        {"dataset": "batting", "measures": ["runs"], "limit": 51},
        {"dataset": "batting", "measures": ["runs"], "series": 9},
        {"dataset": "batting", "measures": [f"m{i}" for i in range(7)]},
        {"dataset": "batting", "measures": ["runs"], "filters": {"players": list("abcdefg")}},
    ],
)
def test_bad_specs_are_422(client: TestClient, spec: dict[str, Any]) -> None:
    response = client.post("/api/v2/ipl/studio/query", json=spec)
    assert response.status_code == 422, response.text


def test_a_season_split_keeps_the_latest_seasons_in_order(
    client: TestClient, serving: duckdb.DuckDBPyConnection
) -> None:
    seasons = [
        int(y)
        for (y,) in serving.execute(
            "SELECT DISTINCT season FROM player_batting_innings ORDER BY season"
        ).fetchall()
    ]
    assert len(seasons) > 3
    body = _run(
        client,
        dataset="batting",
        measures=["runs"],
        group_by="player",
        split_by="season",
        series=3,
        order="desc",
    )
    assert [int(s["group"]["key"]) for s in body["series"]] == seasons[-3:]


def test_the_row_cap_holds(client: TestClient) -> None:
    body = _run(client, dataset="batting", measures=["runs"], limit=3)
    assert len(body["rows"]) == 3
    assert body["truncated"]
    every = _run(client, dataset="batting", measures=["runs"], limit=50)
    assert len(every["rows"]) <= 50
    split = _run(
        client, dataset="batting", measures=["runs"], group_by="player", split_by="season", limit=2
    )
    assert len(split["rows"]) == 2
    assert {c["group"] for c in split["cells"]} <= {r["group"]["key"] for r in split["rows"]}


def test_wpa_is_missing_before_scoring(unscored_client: TestClient) -> None:
    options = unscored_client.get("/api/v2/ipl/studio/options").json()
    batting = next(d for d in options["datasets"] if d["key"] == "batting")
    assert "wpa" not in {m["key"] for m in batting["measures"]}
    response = unscored_client.post(
        "/api/v2/ipl/studio/query", json={"dataset": "batting", "measures": ["wpa"]}
    )
    assert response.status_code == 422


def test_tests_have_their_own_phases(client: TestClient) -> None:
    rows = _run(client, "test", dataset="phase_bowling", measures=["wickets"], group_by="phase")[
        "rows"
    ]
    assert [r["group"]["label"] for r in rows] == ["New ball", "Middle overs", "Second new ball"]
    drawn = _run(client, "test", dataset="teams", measures=["drawn"], group_by=None)["rows"]
    assert drawn[0]["values"]["drawn"] is not None


def test_figures_are_written_as_cricket_writes_them() -> None:
    assert _figure("score", 175 * 2 + 1) == (175.0, "175*")
    assert _figure("figures", 5 * 1000 + 999 - 27) == (5.0, "5/27")
    assert _figure("overs", 123) == (20.5, "20.3")
    assert _figure("overs", 24) == (4.0, "4")
    assert _figure("pct", 42.13) == (42.13, "42.1%")
    assert _figure("signed", 12.34) == (12.34, "+12.3")
    assert _figure("wpa", -0.0) == (0.0, "+0.00")
    assert _figure("rate", None) == (None, chr(0x2014))
    assert _figure("count", 9336) == (9336.0, "9,336")


def test_a_slow_query_is_interrupted(fixture_scored_serving_db: Path) -> None:
    db = Database(fixture_scored_serving_db)
    try:
        with pytest.raises(QueryTimeoutError):
            db.rows(
                "SELECT count(*) FROM range(1000000000) a, range(1000) b "
                "WHERE a.range % 7 = b.range",
                timeout=0.2,
            )
        assert db.scalar("SELECT 1") == 1  # the connection still works
    finally:
        db.close()
