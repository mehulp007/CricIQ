"""The training protocol end to end, on the fixture matches with a tiny grid."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_ml import registry
from criciq_ml.config import load_config
from criciq_ml.model import WinProbabilityModel
from criciq_ml.training import TrainResult, evaluable, train_model


@pytest.fixture(scope="module")
def trained(fixture_states: pd.DataFrame) -> TrainResult:
    cfg = load_config().model_copy(deep=True)
    cfg.splits.train_through = 2019
    cfg.splits.validation = [2020, 2022]
    cfg.splits.test = [2023, 2025]
    cfg.splits.backtest_from = 2020
    cfg.lightgbm.base.update(max_rounds=30, early_stopping_rounds=10)
    cfg.lightgbm.grid = {"num_leaves": [4], "min_data_in_leaf": [20], "recency_half_life": [0]}
    return train_model(fixture_states, cfg, data_version="fixture")


def test_evaluation_reports_every_comparison(trained: TrainResult) -> None:
    ev = trained.evaluation
    assert ev["calibration"]["method"] in {"none", "platt"}
    test = ev["test"]
    for key in ("model", "baseline", "state_only"):
        assert 0 < test[key]["log_loss"] < 5
        assert 0 <= test[key]["brier"] <= 1
    assert {a["key"] for a in test["alternatives"]} >= {"isotonic"}
    assert test["vs_baseline"]["ci_low"] <= test["vs_baseline"]["ci_high"]
    assert sum(b["count"] for b in test["reliability"]) == test["model"]["rows"]
    assert [r["season"] for r in ev["backtest"]] == [2020, 2022, 2023, 2025]
    assert {r["variant"] for r in ev["feature_selection"]} >= {"served", "+venue"}
    assert sum(ev["importance"].values()) == pytest.approx(1.0)


def test_served_model_predicts_probabilities(
    trained: TrainResult, fixture_states: pd.DataFrame
) -> None:
    scored = trained.model.score(fixture_states)
    assert scored["wp_batting"].between(0, 1).all()
    assert trained.model.manifest["trained_on"]["seasons"] == [2008, 2025]


def test_final_ball_of_a_finished_chase_is_not_evaluated(fixture_states: pd.DataFrame) -> None:
    kept = evaluable(fixture_states)
    chase = fixture_states[fixture_states["innings_no"] == 2]
    finals = chase.groupby("match_id")["seq_no"].max()
    assert len(fixture_states) - len(kept) == len(finals)


def test_registry_save_load_and_gate(
    trained: TrainResult, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRICIQ_MODELS_DIR", str(tmp_path))
    registry.save(trained.model, trained.evaluation)
    registry.promote(trained.model.version)
    assert registry.current_version() == trained.model.version
    loaded = registry.load_current()
    assert isinstance(loaded, WinProbabilityModel)
    assert registry.load_evaluation(trained.model.version)["version"] == trained.model.version

    good = {"splits": {"test": [2025]}, "test": _test(0.50, 0.17, 0.55, 0.18)}
    assert registry.gate(good, None, 0.002) == []
    worse_than_baseline = {"splits": {"test": [2025]}, "test": _test(0.56, 0.19, 0.55, 0.18)}
    assert len(registry.gate(worse_than_baseline, None, 0.002)) == 2
    regressed = {"splits": {"test": [2025]}, "test": _test(0.53, 0.17, 0.55, 0.18)}
    assert registry.gate(regressed, good, 0.002)


def _test(loss: float, brier: float, base_loss: float, base_brier: float) -> dict[str, object]:
    return {
        "model": {"log_loss": loss, "brier": brier},
        "baseline": {"log_loss": base_loss, "brier": base_brier},
    }


def test_metrics_behave() -> None:
    from criciq_ml import metrics

    y = np.array([0.0, 1.0, 1.0, 0.5])
    perfect = np.array([0.0, 1.0, 1.0, 0.5])
    assert metrics.brier(y, perfect) == 0
    assert metrics.log_loss(y, np.full(4, 0.5)) == pytest.approx(np.log(2))
    assert metrics.auc(y, np.array([0.1, 0.9, 0.8, 0.5])) == 1.0
    boot = metrics.paired_bootstrap(np.array([1, 1, 2, 2]), y, perfect, np.full(4, 0.5))
    assert boot["improvement"] > 0
