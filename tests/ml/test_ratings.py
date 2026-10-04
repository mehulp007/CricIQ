"""CricIQ Ratings fit: shrinkage constants, evaluation and the registry artifact."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_core.ratings import components
from criciq_ml import ratings, ratings_report, registry
from criciq_ml.ratings import (
    RatingsModel,
    _pairs,
    load_ratings_config,
    noise_variance,
    season_sums,
    train_ratings,
    tune_k,
)

SCORING = next(c for c in components() if c.role == "batting" and c.key == "scoring")


def _synthetic(
    players: int = 400, seasons: int = 8, tau: float = 0.12, sigma: float = 1.5, seed: int = 7
) -> pd.DataFrame:
    """Innings with a persistent per-player talent plus per-ball noise.

    For constant talent the best linear predictor of the next season shrinks
    a season's record towards the mean with k = sigma^2 / tau^2 balls.
    """
    rng = np.random.default_rng(seed)
    talent = rng.normal(0.0, tau, players)
    rows = []
    for p in range(players):
        innings = rng.integers(4, 16)
        for season in range(2010, 2010 + seasons):
            for _ in range(innings):
                n = int(rng.integers(5, 40))
                e = talent[p] * n + rng.normal(0.0, sigma * np.sqrt(n))
                rows.append(("scoring", f"p{p}", season, e, float(n)))
    return pd.DataFrame(rows, columns=["component", "player_id", "season", "e", "n"])


def test_noise_variance_recovers_the_per_ball_noise() -> None:
    units = _synthetic()
    assert noise_variance(units) == pytest.approx(1.5**2, rel=0.05)


def test_tuned_k_matches_the_signal_to_noise_ratio() -> None:
    units = _synthetic()
    component = dataclasses.replace(SCORING, qualify=0)
    sums = season_sums(units, component, factor=0.0)
    grid = np.geomspace(1, 5000, 200)
    k = tune_k(_pairs(sums), grid)
    assert k == pytest.approx(1.5**2 / 0.12**2, rel=0.35)


def test_no_signal_means_heavy_shrinkage() -> None:
    units = _synthetic(tau=0.0)
    sums = season_sums(units, dataclasses.replace(SCORING, qualify=0), factor=0.0)
    assert tune_k(_pairs(sums), np.geomspace(1, 20000, 100)) > 3000


def test_tuning_never_uses_the_future_seasons() -> None:
    units = _synthetic()
    sums = season_sums(units, dataclasses.replace(SCORING, qualify=0), factor=0.0)
    pairs = _pairs(sums)
    early = pairs[pairs["season"] + 1 < 2014]
    assert set(early["season"]) == {2010, 2011, 2012}
    assert tune_k(early, np.geomspace(1, 5000, 50)) > 0


def test_gate_requires_shrinkage_to_beat_the_raw_record() -> None:
    good = {
        "role": "batting",
        "key": "x",
        "next_season": {"mse": {"par": 2, "raw": 3, "shrunk": 1}},
    }
    bad = {"role": "bowling", "key": "y", "next_season": {"mse": {"par": 1, "raw": 1, "shrunk": 1}}}
    empty = {"role": "bowling", "key": "z", "next_season": {"pairs": 0}}
    assert ratings.gate({"components": [good, empty]}) == []
    problems = ratings.gate({"components": [good, bad]})
    assert len(problems) == 1
    assert "bowling y" in problems[0]


def test_fit_runs_on_the_fixture_data(fixture_scored_serving_db: Path, tmp_path: Path) -> None:
    cfg = load_ratings_config()
    model, evaluation = train_ratings(fixture_scored_serving_db, cfg, data_version="fixture")
    served = model.manifest["components"]
    assert set(served) == {"batting", "bowling"}
    assert {"scoring", "survival", "death", "chasing", "impact", "consistency"} <= set(
        served["batting"]
    )
    assert {"economy", "wickets", "defending", "impact"} <= set(served["bowling"])
    for constants in (c for role in served.values() for c in role.values()):
        assert constants["k"] > 0
        assert constants["sigma2"] > 0
        assert constants["stability"] in {"high", "moderate", "low"}
    assert len(evaluation["components"]) == sum(len(v) for v in served.values())
    assert set(evaluation["similarity"]) == {"batting", "bowling"}

    model.save(tmp_path / "ratings")
    assert RatingsModel.load(tmp_path / "ratings").manifest == model.manifest


def test_committed_ratings_are_promoted_and_reported() -> None:
    version = registry.current_version(registry.RATINGS)
    assert version is not None
    model = registry.load_current_ratings()
    assert model.version == version
    data = ratings_report.insights(version)
    card = ratings_report.model_card(data)
    for c in data["components"]:
        assert c["label"] in card
    bundled = json.loads(ratings_report.INSIGHTS_PATH.read_text(encoding="utf-8"))
    assert bundled == data
    assert ratings.gate(registry.load_evaluation(version, registry.RATINGS)) == []
