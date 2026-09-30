import copy
from itertools import pairwise

import pytest

from criciq_pipelines.extract import ExtractError, parse_match
from tests.conftest import load_match


def _innings(rows: dict[str, list[dict[str, object]]], number: int) -> list[dict[str, object]]:
    return [d for d in rows["deliveries"] if d["innings_no"] == number]


def test_2008_opener_scorecard() -> None:
    rows = parse_match(335982, load_match(335982))
    match = rows["matches"][0]
    assert {match["team1"], match["team2"]} == {
        "Kolkata Knight Riders",
        "Royal Challengers Bangalore",
    }
    assert match["outcome_winner"] == "Kolkata Knight Riders"
    assert match["outcome_by_runs"] == 140

    kkr, rcb = _innings(rows, 1), _innings(rows, 2)
    assert sum(d["runs_total"] for d in kkr) == 222  # type: ignore[misc]
    assert kkr[-1]["legal_ball_no"] == 120
    assert sum(d["runs_total"] for d in rcb) == 82  # type: ignore[misc]
    assert rcb[-1]["legal_ball_no"] == 91  # all out in 15.1 overs


def test_wides_and_noballs_are_not_legal() -> None:
    rows = parse_match(335982, load_match(335982))
    for delivery in rows["deliveries"]:
        illegal = bool(delivery["extras_wides"]) or bool(delivery["extras_noballs"])
        assert delivery["is_legal"] is (not illegal)
    # legal_ball_no never advances on an illegal delivery
    innings = _innings(rows, 1)
    for previous, current in pairwise(innings):
        step = int(str(current["legal_ball_no"])) - int(str(previous["legal_ball_no"]))
        assert step == (1 if current["is_legal"] else 0)


def test_super_over_innings_are_flagged() -> None:
    rows = parse_match(1216517, load_match(1216517))
    flags = [i["is_super_over"] for i in rows["innings"]]
    assert flags == [False, False, True, True, True, True]


def test_revised_target_is_kept_with_fractional_overs() -> None:
    rows = parse_match(392186, load_match(392186))
    chase = rows["innings"][1]
    assert chase["target_overs"] == 9.2
    assert rows["matches"][0]["outcome_method"] == "D/L"


def test_no_result_has_single_innings() -> None:
    rows = parse_match(1359519, load_match(1359519))
    assert rows["matches"][0]["outcome_result"] == "no result"
    assert len(rows["innings"]) == 1


def test_impact_player_replacement_is_extracted() -> None:
    rows = parse_match(1473511, load_match(1473511))
    impact = [r for r in rows["replacements"] if r["reason"] == "impact_player"]
    assert len(impact) == 2  # one per side
    assert all(r["kind"] == "match" and r["player_in_id"] and r["player_out_id"] for r in impact)


def test_names_resolve_through_registry() -> None:
    rows = parse_match(335982, load_match(335982))
    ids = {d["batter_id"] for d in rows["deliveries"]}
    assert all(isinstance(i, str) and len(i) == 8 for i in ids)


def test_unknown_name_fails_loudly() -> None:
    doc = copy.deepcopy(load_match(335982))
    doc["innings"][0]["overs"][0]["deliveries"][0]["batter"] = "Nobody"
    with pytest.raises(ExtractError, match="Nobody"):
        parse_match(335982, doc)


def test_inconsistent_runs_fail_loudly() -> None:
    doc = copy.deepcopy(load_match(335982))
    doc["innings"][0]["overs"][0]["deliveries"][0]["runs"]["total"] += 1
    with pytest.raises(ExtractError, match="runs mismatch"):
        parse_match(335982, doc)
