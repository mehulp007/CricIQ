"""First-innings score projection: target, calibration, probabilities and the served model."""

import json
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_ml import projection_report, registry
from criciq_ml.projection import (
    LEVELS,
    MEDIAN,
    TARGET,
    ScoreProjectionModel,
    conformal_shifts,
    probability_at_least,
    projection_frame,
    trainable,
)
from criciq_ml.projection_training import load_projection_config, train_projection

FINAL_2019 = 1181768
ERA_RPB = 1.45


@pytest.fixture(scope="module")
def model() -> ScoreProjectionModel:
    return registry.load_current_projection("IPL")


def test_target_is_the_rest_of_the_innings(fixture_states: pd.DataFrame) -> None:
    frame = projection_frame(fixture_states)
    final = frame[frame["match_id"] == FINAL_2019]
    assert set(final["final_runs"]) == {149}
    assert final["complete"].all()
    assert (frame["innings_no"] == 1).all()
    play = final[final["projectable"]]
    rest = play[TARGET] * play["expected_rest"]
    np.testing.assert_allclose(rest, 149 - play["runs"])
    assert not final.iloc[-1]["projectable"]  # nothing left to project after the last ball


def test_conformal_shifts_hit_each_level() -> None:
    rng = np.random.default_rng(3)
    target = rng.normal(1.0, 0.3, 5000)
    raw = np.tile(np.array(LEVELS) - 0.5 + 1.0, (5000, 1))  # a badly placed forecast
    shifted = np.sort(raw, axis=1) + conformal_shifts(raw, target)
    observed = (target[:, None] <= shifted).mean(axis=0)
    np.testing.assert_allclose(observed, LEVELS, atol=0.005)


def test_probability_of_passing_a_total() -> None:
    quantiles = np.array([[150.0, 155, 162, 170, 178, 185, 190]])
    current = np.array([120.0])
    assert probability_at_least(quantiles, current, 110)[0] == 1.0
    assert probability_at_least(quantiles, current, 170)[0] == pytest.approx(0.5)
    probs = [probability_at_least(quantiles, current, t)[0] for t in range(120, 240, 5)]
    assert all(a >= b for a, b in pairwise(probs))
    assert probs[-1] == 0.0


def _state(runs: int, legal: int, wickets: int) -> dict[str, float]:
    return {
        "runs": runs,
        "legal_balls": legal,
        "balls_remaining": 120 - legal,
        "wickets": wickets,
        "env_rpb": ERA_RPB,
        "expected_rest": ERA_RPB * (120 - legal),
        "runs_vs_par": runs - ERA_RPB * legal,
        "run_rate_rel": runs / (ERA_RPB * legal),
        "runs_last_12": 18,
        "wickets_last_12": 0,
    }


def test_served_projection_is_sane(model: ScoreProjectionModel) -> None:
    by_wickets = model.predict(pd.DataFrame([_state(80, 60, w) for w in range(9)]))
    by_runs = model.predict(pd.DataFrame([_state(r, 60, 3) for r in range(50, 120, 10)]))
    for quantiles in (by_wickets, by_runs):
        assert (np.diff(quantiles, axis=1) >= 0).all(), "quantiles never cross"
    assert (by_wickets[:, 0] >= 80).all(), "never below the current score"
    # Wickets are not a hard constraint (LightGBM quantiles cannot take one), so
    # check the direction overall rather than step by step.
    medians = by_wickets[:, MEDIAN]
    assert medians[0] - medians[-1] > 15
    assert np.mean(np.diff(medians) <= 0.5) >= 0.75
    assert by_runs[-1, MEDIAN] > by_runs[0, MEDIAN] + 40


def test_model_round_trips(model: ScoreProjectionModel, tmp_path: Path) -> None:
    model.save(tmp_path)
    loaded = ScoreProjectionModel.load(tmp_path)
    frame = pd.DataFrame([_state(95, 72, 2)])
    np.testing.assert_allclose(loaded.predict(frame), model.predict(frame))


def test_training_protocol_runs_end_to_end(fixture_states: pd.DataFrame) -> None:
    cfg = load_projection_config().model_copy(deep=True)
    cfg.splits.tune_train_through = 2017
    cfg.splits.tune_valid = [2019, 2020]
    cfg.splits.calibrate = [2022, 2023]
    cfg.splits.test = [2025]
    cfg.splits.backtest_from = 2023
    cfg.lightgbm["base"].update(max_rounds=20, early_stopping_rounds=5)
    cfg.lightgbm["grid"] = {"num_leaves": [4], "min_data_in_leaf": [10]}
    trained, evaluation, _ = train_projection(fixture_states, cfg, data_version="fixture")
    test = evaluation["test"]
    assert 0 <= test["model"]["coverage80"] <= 1
    assert test["model"]["mae"] > 0
    assert {r["variant"] for r in evaluation["feature_selection"]} >= {"served", "+venue"}
    assert [r["season"] for r in evaluation["backtest"]] == [2023, 2025]
    frame = trainable(projection_frame(fixture_states))
    assert trained.predict(frame).shape == (len(frame), len(LEVELS))


def test_projection_gate() -> None:
    def evaluation(coverage: float, mae: float) -> dict[str, object]:
        return {
            "test": {
                "model": {"coverage80": coverage, "mae": mae, "pinball": 4.8},
                "par_baseline": {"mae": 18.0, "pinball": 5.4},
            }
        }

    assert registry.projection_gate(evaluation(0.80, 16.0), [0.75, 0.85]) == []
    assert len(registry.projection_gate(evaluation(0.70, 19.0), [0.75, 0.85])) == 2


def test_bundled_projection_insights_match_the_registry() -> None:
    bundled = json.loads(projection_report.INSIGHTS_PATH.read_text(encoding="utf-8"))
    version = registry.current_version(registry.PROJECTION, "IPL")
    assert version is not None
    evaluation = registry.load_evaluation(version, registry.PROJECTION)
    assert bundled["version"] == version
    assert bundled["test"]["model"] == evaluation["test"]["model"]
    card = projection_report.model_card(projection_report.insights(version))
    assert f"{evaluation['test']['model']['mae']:.2f}" in card
