from pathlib import Path

import pytest

from criciq_pipelines.enrich import (
    apply_overrides,
    build_rows,
    infobox_field,
    normalize_batting,
    normalize_bowling,
    normalize_country,
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
