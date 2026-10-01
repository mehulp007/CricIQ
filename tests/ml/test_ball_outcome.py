"""Ball-outcome model, head-to-head shrinkage and their serving form."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_api.services.matchups import BallModel
from criciq_ml.ball_outcome import (
    CLASSES,
    GROUPS,
    BallOutcomeModel,
    MarginalBaseline,
    add_situation,
    fit_kappa,
    load_balls,
    log_loss,
    outcome_index,
    pair_counts,
)


@pytest.fixture(scope="module")
def balls(fixture_warehouse: Path) -> pd.DataFrame:
    return load_balls(fixture_warehouse)


@pytest.fixture(scope="module")
def model(balls: pd.DataFrame) -> BallOutcomeModel:
    fitted = BallOutcomeModel.fit(balls, player_scale=0.1, c=1.0, max_iter=2000)
    fitted.manifest.update({"name": "ball_outcome", "version": "test", "kappa": 300.0})
    return fitted


def test_outcomes_follow_the_runs_and_bowler_credited_wickets() -> None:
    runs = [0, 1, 2, 3, 4, 5, 6, 0, 1]
    out = [False] * 7 + [True, False]
    assert [CLASSES[i] for i in outcome_index(runs, out)] == [
        "dot",
        "one",
        "two",
        "three",
        "four",
        "three",
        "six",
        "out",
        "one",
    ]


def test_every_ball_faced_is_included_once(balls: pd.DataFrame, fixture_warehouse: Path) -> None:
    import duckdb

    con = duckdb.connect(str(fixture_warehouse), read_only=True)
    faced = con.execute(
        """
        SELECT count(*) FROM deliveries JOIN innings USING (match_id, innings_no)
        WHERE NOT is_super_over AND extras_wides = 0
        """
    ).fetchone()
    con.close()
    assert faced == (len(balls),)
    assert not balls.duplicated(["match_id", "innings_no", "seq_no"]).any()
    for group, levels in GROUPS.items():
        assert set(balls[f"g_{group}"]) - set(levels) <= {"right_unknown", "left_unknown"} | {
            f"unknown_{t}" for t in ("pace", "spin", "unknown")
        }, group


def test_scoring_era_only_looks_back(balls: pd.DataFrame) -> None:
    """Dropping later matches never changes an earlier match's era."""
    orders = sorted(balls["match_order"].unique())
    cut = orders[len(orders) // 2]
    raw = balls.drop(columns=[c for c in balls.columns if c.startswith("g_")] + ["env", "outcome"])
    early = add_situation(raw[raw["match_order"] <= cut])
    full = balls[balls["match_order"] <= cut]
    assert np.allclose(early["env"].to_numpy(), full["env"].to_numpy())
    first = balls[balls["match_order"] == orders[0]]
    assert (first["env"] == 1.2).all()


def test_predictions_are_distributions(model: BallOutcomeModel, balls: pd.DataFrame) -> None:
    probs = model.predict(balls)
    assert probs.shape == (len(balls), len(CLASSES))
    assert np.allclose(probs.sum(axis=1), 1.0)
    assert (probs > 0).all()
    # Fitted in sample, it must beat outcome frequencies that ignore the situation.
    flat = np.bincount(balls["outcome"], minlength=len(CLASSES)) / len(balls)
    assert log_loss(probs, balls["outcome"]) < log_loss(
        np.tile(flat, (len(balls), 1)), balls["outcome"]
    )


def test_save_and_load_round_trip(
    model: BallOutcomeModel, balls: pd.DataFrame, tmp_path: Path
) -> None:
    model.save(tmp_path)
    loaded = BallOutcomeModel.load(tmp_path)
    assert np.allclose(loaded.predict(balls), model.predict(balls), atol=1e-5)


def test_api_arithmetic_matches_the_model(model: BallOutcomeModel, balls: pd.DataFrame) -> None:
    """The API evaluates the stored terms without numpy; it must agree with the model."""
    served = BallModel(
        version="test",
        kappa=300.0,
        env_now=float(balls["env"].iloc[-1]),
        env_mean=model.manifest["env_mean"],
        env_std=model.manifest["env_std"],
        terms={k: list(map(float, v)) for k, v in model.terms.items()},
    )
    sample = balls.sample(25, random_state=3)
    expected = model.predict(sample)
    for row, probs in zip(sample.itertuples(index=False), expected, strict=True):
        served_env = BallModel(**{**served.__dict__, "env_now": float(row.env)})
        got = served_env.probabilities(
            batter_id=row.batter_id,
            bowler_id=row.bowler_id,
            phase=row.phase,
            innings=row.innings_no,
            wickets=row.wickets_before,
            batter_balls=row.batter_balls,
            matchup=row.g_matchup,
            pressure=row.g_pressure,
        )
        assert np.allclose(got, probs, atol=1e-9)


def test_baseline_is_a_distribution(balls: pd.DataFrame) -> None:
    probs = MarginalBaseline(balls).predict(balls)
    assert np.allclose(probs.sum(axis=1), 1.0)


def test_pair_counts_add_up(model: BallOutcomeModel, balls: pd.DataFrame) -> None:
    pairs = pair_counts(balls, model.predict(balls))
    observed = pairs[[f"n_{c}" for c in CLASSES]].to_numpy()
    expected = pairs[[f"e_{c}" for c in CLASSES]].to_numpy()
    assert observed.sum() == pytest.approx(len(balls))
    assert np.allclose(observed.sum(axis=1), expected.sum(axis=1))


def test_kappa_recovers_a_known_prior_strength() -> None:
    rng = np.random.default_rng(11)
    prior = np.array([0.33, 0.38, 0.06, 0.01, 0.12, 0.05, 0.05])
    true_kappa = 80.0
    pairs = 4000
    totals = rng.integers(5, 60, size=pairs)
    rates = rng.dirichlet(true_kappa * prior, size=pairs)
    counts = np.stack([rng.multinomial(n, p) for n, p in zip(totals, rates, strict=True)])
    estimate = fit_kappa(counts.astype(float), np.tile(prior, (pairs, 1)))
    assert 55 < estimate < 115
    # Pure noise around the prior: the estimate runs to the top of the range.
    noise = np.stack([rng.multinomial(n, prior) for n in totals]).astype(float)
    assert fit_kappa(noise, np.tile(prior, (pairs, 1))) > 2000
