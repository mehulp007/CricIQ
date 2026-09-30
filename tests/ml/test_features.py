"""Win probability features: correct match state, and no peeking at the future."""

from dataclasses import replace
from pathlib import Path

import pandas as pd

from criciq_ml.data import Inputs, load_inputs
from criciq_ml.features import (
    CANDIDATES,
    FEATURES,
    FORBIDDEN,
    GROUPS,
    LABEL,
    MONOTONE,
    build_states,
)

FINAL_2019 = 1181768
TIE_2020 = 1216517


def _cutoff(inputs: Inputs) -> int:
    return int(sorted(inputs.matches["match_order"])[len(inputs.matches) // 2])


def _earlier(states: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    return states[states["match_order"] <= cutoff].reset_index(drop=True)


def test_features_do_not_change_when_later_matches_are_removed(fixture_warehouse: Path) -> None:
    inputs = load_inputs(fixture_warehouse)
    cutoff = _cutoff(inputs)
    full = build_states(inputs)
    truncated = build_states(inputs.up_to(cutoff))
    pd.testing.assert_frame_equal(_earlier(full, cutoff), truncated.reset_index(drop=True))


def test_features_do_not_change_when_later_matches_are_rewritten(
    fixture_warehouse: Path,
) -> None:
    inputs = load_inputs(fixture_warehouse)
    cutoff = _cutoff(inputs)
    later = set(inputs.matches.loc[inputs.matches["match_order"] > cutoff, "match_id"])

    deliveries = inputs.deliveries.copy()
    rows = deliveries["match_id"].isin(later)
    deliveries.loc[rows, ["runs_batter", "runs_total"]] += 6
    deliveries.loc[rows, "team_runs"] += 100
    matches = inputs.matches.copy()
    matches.loc[matches["match_id"].isin(later), "outcome_type"] = "tie"
    tampered = replace(inputs, deliveries=deliveries, matches=matches)

    pd.testing.assert_frame_equal(
        _earlier(build_states(inputs), cutoff), _earlier(build_states(tampered), cutoff)
    )


def test_served_features_are_allowlisted_and_explained(fixture_states: pd.DataFrame) -> None:
    for number, features in FEATURES.items():
        assert set(features) <= set(fixture_states.columns)
        assert not set(features) & FORBIDDEN
        explained = [f for group in GROUPS.values() for f in group[number]]
        assert sorted(explained) == sorted(features), "every feature in exactly one group"
        assert set(MONOTONE[number]) <= set(features)
        for candidate in CANDIDATES.values():
            assert set(candidate[number]) <= set(fixture_states.columns)


def test_states_follow_the_scoreboard(fixture_states: pd.DataFrame) -> None:
    final = fixture_states[fixture_states["match_id"] == FINAL_2019]
    first = final[final["innings_no"] == 1]
    chase = final[final["innings_no"] == 2]

    start = first.iloc[0]
    assert (start["seq_no"], start["runs"], start["wickets"], start["legal_balls"]) == (0, 0, 0, 0)
    assert (first.iloc[-1]["runs"], first.iloc[-1]["wickets"]) == (149, 8)

    opening = chase.iloc[0]
    assert (opening["runs_needed"], opening["balls_remaining"]) == (150, 120)
    assert opening["required_rate"] == 7.5
    end = chase.iloc[-1]
    assert (end["runs"], end["wickets"], end["runs_needed"], end["balls_remaining"]) == (
        148,
        7,
        2,
        0,
    )
    # Mumbai (batting first) won; ties are half a win.
    assert set(first[LABEL]) == {1.0}
    assert set(chase[LABEL]) == {0.0}
    tie = fixture_states[fixture_states["match_id"] == TIE_2020]
    assert set(tie[LABEL]) == {0.5}


def test_recent_form_window_is_bounded(fixture_states: pd.DataFrame) -> None:
    assert (fixture_states["runs_last_12"] <= fixture_states["runs"]).all()
    assert (fixture_states["wickets_last_12"] <= fixture_states["wickets"]).all()
    assert fixture_states["wickets_last_12"].max() <= 12


def test_chase_probability_feature_is_a_probability(fixture_states: pd.DataFrame) -> None:
    chase = fixture_states[fixture_states["innings_no"] == 2]
    assert chase["chase_dp"].between(0, 1).all()
    assert fixture_states.loc[fixture_states["innings_no"] == 1, "chase_dp"].isna().all()
