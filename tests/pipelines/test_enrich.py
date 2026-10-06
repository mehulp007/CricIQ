from __future__ import annotations

import io
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path

import duckdb
import pytest

from criciq_core import paths
from criciq_pipelines import enrich, pipeline
from criciq_pipelines.enrich import (
    _get_json,
    apply_overrides,
    build_rows,
    infobox_field,
    normalize_batting,
    normalize_bowling,
    normalize_country,
    read_rows,
    write_rows,
)

WIKITEXT = """{{Infobox cricketer
| name = Example Player
| country = [[India national cricket team|India]]<ref>{{cite web|url=x}}</ref>
| batting = Right-handed
| bowling = {{ubl|Right-arm [[fast bowling|fast-medium]]|Right-arm [[off spin|off break]]}}
| role = [[Bowler (cricket)|Bowler]] <!-- hidden note -->
}}"""


def test_infobox_field_strips_markup() -> None:
    assert infobox_field(WIKITEXT, "country") == "India"
    assert infobox_field(WIKITEXT, "batting") == "Right-handed"
    assert infobox_field(WIKITEXT, "bowling") == "Right-arm fast-medium"
    assert infobox_field(WIKITEXT, "role") == "Bowler"
    assert infobox_field(WIKITEXT, "missing") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Right-handed", "right"),
        ("Left handed", "left"),
        ("left-Handed", "left"),
        ("Right footed", None),
        (None, None),
    ],
)
def test_normalize_batting(text: str | None, expected: str | None) -> None:
    assert normalize_batting(text) == expected


@pytest.mark.parametrize(
    ("text", "arm", "kind", "style"),
    [
        ("Right-arm fast", "right", "pace", "Right-arm fast"),
        ("Right arm fast-medium", "right", "pace", "Right-arm fast-medium"),
        ("Left-arm medium-fast", "left", "pace", "Left-arm medium-fast"),
        ("Slow left-arm orthodox", "left", "spin", "Left-arm orthodox"),
        ("Left-arm unorthodox spin", "left", "spin", "Left-arm wrist spin"),
        ("Legbreak googly", "right", "spin", "Right-arm leg break"),
        ("Right-arm off-spin", "right", "spin", "Right-arm off break"),
        ("Right-arm medium, Right-arm off break", "right", "pace", "Right-arm medium"),
        ("", None, None, None),
    ],
)
def test_normalize_bowling(text: str, arm: str | None, kind: str | None, style: str | None) -> None:
    result = normalize_bowling(text)
    assert (result.arm, result.kind, result.style) == (arm, kind, style)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("India1", "India"),
        ("India (Assam)", "India"),
        ("Bharat", "India"),
        ("UAE", "United Arab Emirates"),
        ("West Indies", "West Indies"),
        ("", None),
    ],
)
def test_normalize_country(text: str, expected: str | None) -> None:
    assert normalize_country(text) == expected


def test_build_rows_prefers_infobox_country_and_falls_back_to_title() -> None:
    wikidata = {
        "1": {
            "qid": "Q1",
            "label": "Q1",
            "citizenship": "Australia",
            "enwiki": "Example Player (cricketer)",
        },
        "2": {"qid": "Q2", "label": "Second Player", "sport_country": "England"},
    }
    rows = build_rows(
        [("p1", "1"), ("p2", "2"), ("p3", "3")], wikidata, {"Example Player (cricketer)": WIKITEXT}
    )
    first, second, third = rows
    assert first["full_name"] == "Example Player"  # Q-id label falls back to the article title
    assert first["country"] == "India"  # infobox beats Wikidata citizenship
    assert (first["batting_hand"], first["bowling_type"]) == ("right", "pace")
    assert second["country"] == "England"
    assert second["batting_hand"] == ""
    assert third["full_name"] == ""
    assert third["source"] == ""


def test_apply_overrides(tmp_path: Path) -> None:
    rows = build_rows([("p1", "1")], {}, {})
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "player_id,field,value,note\np1,country,India,x\np1,batting_hand,left,y\n", "utf-8"
    )
    assert apply_overrides(rows, overrides) == 2
    assert rows[0]["country"] == "India"
    assert rows[0]["batting_hand"] == "left"
    assert rows[0]["source"] == "manual"

    overrides.write_text("player_id,field,value,note\nzzz,country,India,x\n", "utf-8")
    with pytest.raises(ValueError, match="invalid override"):
        apply_overrides(rows, overrides)


def test_rows_round_trip(tmp_path: Path) -> None:
    rows = build_rows([("p2", "2"), ("p1", "1")], {"1": {"label": "One Player"}}, {})
    path = tmp_path / "attributes.csv"
    write_rows(rows, path)
    assert read_rows(path) == {row["player_id"]: row for row in rows}
    assert read_rows(tmp_path / "missing.csv") == {}


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _flaky(failures: list[Exception]) -> Callable[..., _Response]:
    def urlopen(*_: object, **__: object) -> _Response:
        if failures:
            raise failures.pop(0)
        return _Response(b'{"ok": true}')

    return urlopen


def test_requests_are_retried_when_dropped_or_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    throttled = urllib.error.HTTPError("u", 429, "Too Many Requests", Message(), None)
    monkeypatch.setattr(
        urllib.request, "urlopen", _flaky([urllib.error.URLError("reset"), throttled])
    )
    waits: list[float] = []
    assert _get_json("https://example.org", delays=(1.0, 2.0, 3.0), sleep=waits.append) == {
        "ok": True
    }
    assert waits == [1.0, 2.0]


def test_a_missing_page_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = urllib.error.HTTPError("u", 404, "Not Found", Message(), None)
    monkeypatch.setattr(urllib.request, "urlopen", _flaky([missing]))
    waits: list[float] = []
    with pytest.raises(urllib.error.HTTPError):
        _get_json("https://example.org", delays=(1.0,), sleep=waits.append)
    assert waits == []


def test_enrichment_keeps_existing_rows_and_looks_up_the_rest(
    fixture_full_warehouse: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    con = duckdb.connect(str(fixture_full_warehouse), read_only=True)
    try:
        ids = dict(
            con.execute(
                "SELECT player_id, value FROM player_identifiers WHERE source = 'cricinfo' "
                "ORDER BY player_id LIMIT 2"
            ).fetchall()
        )
    finally:
        con.close()
    (kept_id, kept_ci), (new_id, new_ci) = sorted(ids.items())
    reference = tmp_path / "reference"
    reference.mkdir()
    existing = build_rows([(kept_id, kept_ci)], {kept_ci: {"label": "Kept As Is"}}, {})
    write_rows(existing, reference / "player_attributes.csv")
    monkeypatch.setattr(paths, "reference_dir", lambda: reference)

    asked: list[str] = []

    def wikidata(cricinfo_ids: list[str]) -> dict[str, dict[str, str]]:
        asked.extend(cricinfo_ids)
        return {new_ci: {"label": "Found Player", "enwiki": "Found Player"}}

    monkeypatch.setattr(enrich, "fetch_wikidata", wikidata)
    monkeypatch.setattr(
        enrich, "fetch_wikitext", lambda titles: {"Found Player": WIKITEXT} if titles else {}
    )
    counts = pipeline.run_enrich_players(warehouse=fixture_full_warehouse)

    rows = read_rows(reference / "player_attributes.csv")
    assert rows[kept_id] == existing[0]  # untouched
    assert kept_ci not in asked
    assert rows[new_id]["full_name"] == "Found Player"
    assert rows[new_id]["batting_hand"] == "right"
    assert counts["looked_up"] == len(rows) - 1
    assert counts["found_on_wikidata"] == 1
