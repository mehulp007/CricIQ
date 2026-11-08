"""The daily notes API: the latest notes, a day's note, and no notes before any are built."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import duckdb
from fastapi.testclient import TestClient

from criciq_api.core.config import Settings
from criciq_api.main import create_app

FINAL = "2025-06-03"  # the 2025 IPL final


def _get(client: TestClient, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_the_latest_notes_come_first_and_page_back(
    client: TestClient, fixture_notes_db: Path
) -> None:
    con = duckdb.connect(str(fixture_notes_db), read_only=True)
    dates = [
        d.isoformat()
        for (d,) in con.execute("SELECT date FROM notes ORDER BY date DESC").fetchall()
    ]
    con.close()
    first = _get(client, "/api/v2/notes", limit=5)
    assert [n["date"] for n in first["notes"]] == dates[:5]
    assert first["next_before"] == dates[4]
    assert first["method"].startswith("Written automatically from CricIQ's ball-by-ball data")
    older = _get(client, "/api/v2/notes", limit=5, before=first["next_before"])
    assert [n["date"] for n in older["notes"]] == dates[5:10]
    every = _get(client, "/api/v2/notes", limit=100)
    assert [n["date"] for n in every["notes"]] == dates
    assert every["next_before"] is None


def test_a_competition_s_list_leads_with_its_own_news(client: TestClient) -> None:
    ipl = _get(client, "/api/v2/notes", competition="ipl", limit=100)
    assert ipl["notes"]
    assert all("ipl" in n["competitions"] for n in ipl["notes"])
    final = next(n for n in ipl["notes"] if n["date"] == FINAL)
    assert final["headline"] == (
        "Royal Challengers Bengaluru beat Punjab Kings by 6 runs in the IPL 2025 final"
    )
    assert _get(client, "/api/v2/notes", competition="bbl")["notes"] == []


def test_a_day_s_note_in_full(client: TestClient) -> None:
    note = _get(client, f"/api/v2/notes/{FINAL}")
    assert note["slug"] == FINAL
    assert note["competitions"] == ["ipl"]
    assert [i["position"] for i in note["items"]] == list(range(1, len(note["items"]) + 1))
    kinds = {i["kind"]: i for i in note["items"]}
    assert kinds["result"]["links"][0]["href"] == "/ipl/matches/1473511"
    assert kinds["turning_point"]["model"] is True
    assert kinds["result"]["model"] is False
    assert note["figures"]
    figure = note["figures"][0]
    assert figure["career_after"] >= figure["career_before"]
    assert figure["unit"] in ("runs", "wickets")
    assert note["previous"] is not None
    assert note["previous"] < FINAL
    previous = _get(client, f"/api/v2/notes/{note['previous']}")
    assert previous["next"] == FINAL


def test_every_note_date(client: TestClient, unscored_client: TestClient) -> None:
    dates = _get(client, "/api/v2/notes/dates")["dates"]
    listed = [n["date"] for n in _get(client, "/api/v2/notes", limit=100)["notes"]]
    assert dates == listed
    assert _get(unscored_client, "/api/v2/notes/dates")["dates"] == []


def test_unknown_and_bad_dates(client: TestClient) -> None:
    assert client.get("/api/v2/notes/1999-01-01").status_code == 404
    assert client.get("/api/v2/notes/yesterday").status_code == 422
    assert client.get("/api/v2/notes", params={"limit": 0}).status_code == 422
    assert client.get("/api/v2/notes", params={"competition": "IPL; --"}).status_code == 422


def test_no_notes_yet(unscored_client: TestClient) -> None:
    body = _get(unscored_client, "/api/v2/notes")
    assert body["notes"] == []
    assert body["next_before"] is None
    assert body["data_version"] is None
    assert unscored_client.get(f"/api/v2/notes/{FINAL}").status_code == 404


def test_notes_written_while_the_api_runs_are_picked_up(
    fixture_serving_db: Path, fixture_players_db: Path, fixture_notes_db: Path, tmp_path: Path
) -> None:
    target = tmp_path / "notes.duckdb"
    settings = Settings(
        environment="test",
        serving_db=fixture_serving_db,
        players_db=fixture_players_db,
        notes_db=target,
    )
    with TestClient(create_app(settings)) as client:
        assert _get(client, "/api/v2/notes")["notes"] == []
        shutil.copyfile(fixture_notes_db, target)
        assert _get(client, "/api/v2/notes")["notes"]


def test_a_match_s_note(client: TestClient) -> None:
    found = _get(client, "/api/v2/notes/matches/ipl/1473511")
    assert found["date"] == FINAL
    assert found["headline"].startswith("Royal Challengers Bengaluru beat Punjab Kings")
    assert {i["match_id"] for i in found["items"]} == {1473511}
    assert found["items"][0]["kind"] == "result"
    assert client.get("/api/v2/notes/matches/ipl/1").status_code == 404
    assert client.get("/api/v2/notes/matches/IPL!/1").status_code == 422
