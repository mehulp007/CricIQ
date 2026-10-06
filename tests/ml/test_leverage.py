"""Leverage, pressure and momentum from the win probability model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_ml import chase, leverage, registry, scoring
from criciq_ml.data import Inputs, load_inputs
from criciq_ml.features import FEATURES


@pytest.fixture(scope="module")
def inputs(fixture_warehouse: Path) -> Inputs:
    return load_inputs(fixture_warehouse)


@pytest.fixture(scope="module")
def states(fixture_states: pd.DataFrame) -> pd.DataFrame:
    return fixture_states.reset_index(drop=True)


def _outcome(d: pd.Series) -> tuple[int, int, int] | None:
    """(runs, wickets, legal) for a delivery that maps exactly onto one modelled outcome."""
    outs = len(d["out_ids"])
    if not d["is_legal"]:
        return None
    if outs == 1 and d["runs_total"] == 0:
        return (0, 1, 1)
    if outs == 0 and d["runs_total"] in (0, 1, 2, 3, 4, 6):
        return (int(d["runs_total"]), 0, 1)
    return None


def test_rebuilt_states_match_what_actually_followed(states: pd.DataFrame, inputs: Inputs) -> None:
    """Applying the ball that was bowled to a state must reproduce the next state exactly."""
    deliveries = inputs.deliveries.set_index(["match_id", "innings_no", "seq_no"])
    season_of = inputs.matches.set_index("match_id")["season"]
    tables = chase.SeasonTables(inputs.deliveries, inputs.deliveries["match_id"].map(season_of))
    checked = 0
    for innings in (1, 2):
        s = states[states["innings_no"] == innings]
        nxt = s.groupby(["match_id", "innings_no"])["seq_no"].shift(-1)
        pairs = s.assign(next_seq=nxt).dropna(subset=["next_seq"])
        rows = []
        for r in pairs.itertuples():
            d = deliveries.loc[(r.match_id, r.innings_no, int(r.next_seq))]
            outcome = _outcome(d)
            if outcome is not None:
                rows.append((r.Index, int(r.next_seq), *outcome))
        frame = pd.DataFrame(rows, columns=["idx", "next_seq", "runs", "wickets", "legal"])
        for (runs, wickets, legal), group in frame.groupby(["runs", "wickets", "legal"]):
            before = states.loc[group["idx"]]
            drop = leverage._dropping_out(before, inputs)
            rebuilt = leverage._after(before, runs, wickets, legal, drop, tables, innings == 2)
            actual = states.set_index(["match_id", "innings_no", "seq_no"]).loc[
                list(zip(before["match_id"], before["innings_no"], group["next_seq"], strict=True))
            ]
            for feature in FEATURES[innings]:
                np.testing.assert_allclose(
                    rebuilt[feature].to_numpy(dtype=float),
                    actual[feature].to_numpy(dtype=float),
                    rtol=1e-6,
                    atol=1e-6,
                    err_msg=f"innings {innings}, outcome {(runs, wickets)}, {feature}",
                )
            checked += len(group)
    assert checked > 1000


def test_outcome_rates_are_distributions(states: pd.DataFrame, inputs: Inputs) -> None:
    rates = leverage.OutcomeRates.estimate(inputs)
    probs = rates.for_states(states)
    assert probs.shape == (len(states), len(leverage.OUTCOMES))
    np.testing.assert_allclose(probs.sum(axis=1), 1.0)
    assert (probs > 0).all()


def test_swing_is_defined_while_play_goes_on(states: pd.DataFrame, inputs: Inputs) -> None:
    model = registry.load_current(registry.NAME, "IPL")
    swing = leverage.expected_swing(model, states, inputs)
    over = (states["legal_balls"] >= states["max_balls"]) | (states["wickets"] >= 10)
    over |= (states["innings_no"] == 2) & (states["runs"] >= states["target"])
    assert np.isnan(swing[over.to_numpy()]).all()
    live = swing[~over.to_numpy()]
    assert not np.isnan(live).any()
    assert (live >= 0).all()  # zero once a chase is hopeless
    # The last ball of a close chase matters far more than a typical ball.
    final = states.assign(swing=swing)
    close = final[
        (final["innings_no"] == 2)
        & (final["balls_remaining"] == 1)
        & (final["runs_needed"].between(1, 6))
        & (final["wickets"] < 10)
    ]
    assert not close.empty
    assert close["swing"].min() > 4 * np.nanmean(swing)


def test_momentum_is_the_change_over_twelve_legal_balls(states: pd.DataFrame) -> None:
    wp = np.linspace(0.2, 0.8, len(states))
    momentum = leverage.momentum(states, wp)
    one = states[(states["match_id"] == states["match_id"].iloc[0]) & (states["innings_no"] == 1)]
    i = one.index[one["legal_balls"] == 30][-1]
    j = one.index[one["legal_balls"] <= 18][-1]
    assert momentum[i] == pytest.approx(100 * (wp[i] - wp[j]))
    start = one.index[0]
    assert momentum[start] == 0.0
    early = one.index[one["legal_balls"] == 5][-1]
    assert momentum[early] == pytest.approx(100 * (wp[early] - wp[start]))


def test_pressure_is_a_percentile() -> None:
    swing = np.array([0.0, 0.1, 0.2, 0.3, 0.4, np.nan])
    scale = leverage.pressure_scale(swing)
    assert scale["mean_swing"] == pytest.approx(0.2)
    pressure = leverage.pressure(swing, scale["quantiles"])
    assert pressure[0] == 0
    assert pressure[4] == 100
    assert np.isnan(pressure[5])
    assert list(pressure[:5]) == sorted(pressure[:5])


def test_scoring_adds_pressure_columns(states: pd.DataFrame, inputs: Inputs) -> None:
    model = registry.load_current(registry.NAME, "IPL")
    predictions, scale = scoring.add_pressure(
        model, states, scoring.score_states(model, states), inputs
    )
    assert {"leverage", "pressure", "momentum"} <= set(predictions)
    assert predictions["pressure"].dropna().between(0, 100).all()
    assert predictions["leverage"].dropna().mean() == pytest.approx(1.0, rel=0.01)
    assert len(scale["quantiles"]) == 101
