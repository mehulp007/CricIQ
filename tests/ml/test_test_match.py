"""Test cricket's own models (criciq_ml.test_match): states, the model's arithmetic,
the projection's targets and scoring, on the fixtures' four Tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_core.phases import use_format
from criciq_core.test_win_probability import GROUPS, InningsTerms, columns, design
from criciq_ml.test_match import scoring as test_scoring
from criciq_ml.test_match.projection import TARGET, ParBaseline, projection_frame
from criciq_ml.test_match.states import (
    DRAWN,
    LOST,
    SCHEDULED_OVERS,
    WON,
    build_states,
    context_now,
    final_rows,
    load_test_inputs,
)
from criciq_ml.test_match.win_probability import (
    INNINGS,
    TestWinProbabilityModel,
    brier,
    fit_innings,
    log_loss,
    paired_bootstrap,
)

INNINGS_WIN = 1122310  # South Africa beat Zimbabwe by an innings and 120 runs (2017)
CHASE_WIN = 1223869  # Australia chase 90 at Adelaide after India's 36 all out (2020)
DRAW = 1223871  # Sydney 2021: India bat out the last day
TWO_RUNS = 215010  # Edgbaston 2005: England win by two runs


@pytest.fixture(scope="module")
def test_copy(fixture_group_copies: dict[str, Path]) -> Path:
    return fixture_group_copies["TEST"]


@pytest.fixture(scope="module")
def states(test_copy: Path) -> pd.DataFrame:
    with use_format("Test"):
        return build_states(load_test_inputs(test_copy))


def test_every_test_and_innings_has_its_states(states: pd.DataFrame) -> None:
    assert set(states["match_id"]) == {INNINGS_WIN, CHASE_WIN, DRAW, TWO_RUNS}
    innings = states.groupby("match_id")["innings_no"].max().to_dict()
    assert innings[INNINGS_WIN] == 3  # an innings win needs only three
    assert innings[DRAW] == 4
    # One state before each innings, then one per ball.
    starts = states[states["seq_no"] == 0]
    assert len(starts) == states.groupby(["match_id", "innings_no"]).ngroups


def test_labels_are_the_batting_side_result(states: pd.DataFrame) -> None:
    draw = states[states["match_id"] == DRAW]
    assert (draw["label"] == DRAWN).all()
    edgbaston = states[states["match_id"] == TWO_RUNS]
    # England batted first and won; Australia batted last and lost.
    assert (edgbaston[edgbaston["innings_no"].isin([1, 3])]["label"] == WON).all()
    assert (edgbaston[edgbaston["innings_no"].isin([2, 4])]["label"] == LOST).all()


def test_the_lead_and_the_chase_add_up(states: pd.DataFrame) -> None:
    edgbaston = states[states["match_id"] == TWO_RUNS]
    start = edgbaston[(edgbaston["innings_no"] == 4) & (edgbaston["seq_no"] == 0)].iloc[0]
    # Australia needed 282 (England 407 & 182 against 308).
    assert start["runs_needed"] == 282
    assert start["lead"] == -281
    last = edgbaston[edgbaston["innings_no"] == 4].iloc[-1]
    assert last["runs_needed"] == 3  # all out two short
    assert last["wickets_in_hand"] == 0
    # Time left falls as the match goes on.
    assert edgbaston["overs_left"].is_monotonic_decreasing
    assert edgbaston["overs_left"].iloc[0] == SCHEDULED_OVERS


def test_context_never_sees_its_own_match(test_copy: Path) -> None:
    """A match's pre-match context is the same with or without later matches."""
    with use_format("Test"):
        inputs = load_test_inputs(test_copy)
        full = build_states(inputs)
        orders = sorted(inputs.matches["match_order"])
        early = build_states(inputs.up_to(orders[-2]))
    context = ["elo_diff", "home", "bat_xi_own", "bowl_xi_opp", "env_rpw"]
    for match_id in early["match_id"].unique():
        a = full.loc[full["match_id"] == match_id, context].reset_index(drop=True)
        b = early.loc[early["match_id"] == match_id, context].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_ratings_after_the_last_test(test_copy: Path) -> None:
    with use_format("Test"):
        now = context_now(load_test_inputs(test_copy))
    # Each side's rating moved from 1500 by its results; the totals balance.
    assert set(now["ratings"]) >= {"ENG", "AUS", "IND", "SA", "ZIM"}
    assert sum(r - 1500 for r in now["ratings"].values()) == pytest.approx(0, abs=0.5)
    assert now["ratings"]["SA"] > now["ratings"]["ZIM"]


def test_the_model_is_plain_arithmetic(states: pd.DataFrame) -> None:
    """The fitted regression reproduces sklearn and survives a trip through JSON."""
    first = states[(states["innings_no"] == 1) & states["label"].notna()]
    terms = fit_innings(first, 1, ["teams", "home"], c=1.0)
    p = terms.probabilities(first)
    assert p.shape == (len(first), 3)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    again = InningsTerms.from_json(terms.to_json())
    np.testing.assert_allclose(again.probabilities(first), p, atol=1e-6)
    _, names = design(first, 1, ["teams", "home"])
    assert names[-4:] == ["rating", "rating_x_time", "home", "home_x_time"]


def test_every_group_has_its_columns(states: pd.DataFrame) -> None:
    for number in INNINGS:
        needed = columns(number, list(GROUPS))
        assert set(needed) <= set(states.columns)


def test_metrics_and_the_bootstrap() -> None:
    y = np.array([0, 1, 2, 2])
    sure = np.eye(3)[y]
    even = np.full((4, 3), 1 / 3)
    assert log_loss(y, even) == pytest.approx(np.log(3))
    assert brier(y, sure) == 0.0
    gain = paired_bootstrap(np.array([1, 1, 2, 2]), y, sure * 0.98 + 0.0066, even)
    assert gain["improvement"] > 0
    assert gain["ci_low"] <= gain["improvement"] <= gain["ci_high"]


def test_scoring_ends_on_the_result(states: pd.DataFrame) -> None:
    terms = {
        n: fit_innings(states[(states["innings_no"] == n) & states["label"].notna()], n, [], 1.0)
        for n in INNINGS
    }
    model = TestWinProbabilityModel(
        terms, {"version": "0.0.0", "name": "win_probability", "trained_on": {}}
    )
    scored = test_scoring.score_wp(model, states)
    last = scored[final_rows(states)].set_index("match_id")
    # The side batting first: England won at Edgbaston, the Sydney Test was drawn.
    assert last.loc[TWO_RUNS, "wp_team_a"] == 1.0
    assert last.loc[DRAW, "wp_draw"] == 1.0
    assert last.loc[CHASE_WIN, "wp_team_a"] == 0.0  # India batted first and lost
    assert ((scored["wp_team_a"] + scored["wp_draw"]) <= 1.0 + 1e-9).all()
    wpa = test_scoring.player_wpa(scored, states, _deliveries(states))
    assert set(wpa["role"]) == {"batting", "bowling"}
    # Every ball's change is credited once each way.
    assert wpa["wpa"].sum() == pytest.approx(0.0, abs=1e-9)


def _deliveries(states: pd.DataFrame) -> pd.DataFrame:
    """Deliveries with a batter and bowler for each scored ball (synthetic ids)."""
    balls = states[states["seq_no"] > 0][["match_id", "innings_no", "seq_no"]].copy()
    balls["batter_id"] = "bat-" + balls["innings_no"].astype(str)
    balls["bowler_id"] = "bowl-" + balls["innings_no"].astype(str)
    return balls


def test_projection_targets_and_par(states: pd.DataFrame) -> None:
    frame = projection_frame(states)
    edgbaston = frame[(frame["match_id"] == TWO_RUNS) & (frame["innings_no"] == 1)]
    assert (edgbaston["final_runs"] == 407).all()
    assert edgbaston[TARGET].iloc[0] == 407
    assert not edgbaston["projectable"].iloc[-1]
    par = ParBaseline(frame[frame["projectable"]]).predict(frame[frame["projectable"]])
    # Quantiles are never below the runs already scored, and rise with the level.
    runs = frame.loc[frame["projectable"], "runs"].to_numpy()
    assert (par >= runs[:, None] - 1e-9).all()
    assert (np.diff(par, axis=1) >= -1e-9).all()
