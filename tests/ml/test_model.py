"""Sanity suite for the served (committed) win probability model."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_ml import chase, registry
from criciq_ml.model import Platt, WinProbabilityModel, terminal_probability

ERA_RPB = 1.45  # runs per ball, roughly the 2024-26 scoring rate


@pytest.fixture(scope="module")
def model() -> WinProbabilityModel:
    return registry.load_current(registry.NAME, "IPL")


@pytest.fixture(scope="module")
def table() -> chase.Table:
    return chase.solve({low: chase.PRIOR for low, _ in chase.BUCKETS})


def first_innings(runs: int, legal: int, wickets: int) -> dict[str, float]:
    return {
        "innings_no": 1,
        "legal_balls": legal,
        "runs": runs,
        "wickets": wickets,
        "runs_vs_par": runs - ERA_RPB * legal,
        "runs_last_12": min(runs, 18),
        "wickets_last_12": min(wickets, 1),
    }


def chase_state(needed: int, left: int, wickets: int, table: chase.Table) -> dict[str, float]:
    rate = min(needed * 6 / left, 36.0) if left else 36.0
    return {
        "innings_no": 2,
        "legal_balls": 120 - left,
        "balls_remaining": left,
        "runs_needed": needed,
        "wickets": wickets,
        "required_rate": rate,
        "chase_ratio": math.log1p(needed) - math.log1p(left),
        "required_rate_rel": rate / (6 * ERA_RPB),
        "chase_dp": chase.lookup(table, needed, left, wickets),
        "runs_last_12": 16,
        "wickets_last_12": 0,
    }


def wp(model: WinProbabilityModel, rows: list[dict[str, float]]) -> np.ndarray:
    frame = pd.DataFrame(rows)
    return model.innings[int(frame["innings_no"].iloc[0])].predict(frame)


def test_more_runs_and_fewer_wickets_never_hurt_the_batting_side(
    model: WinProbabilityModel,
) -> None:
    by_runs = wp(model, [first_innings(r, 60, 3) for r in range(40, 160, 5)])
    by_wickets = wp(model, [first_innings(90, 60, w) for w in range(10)])
    assert (np.diff(by_runs) >= -1e-9).all()
    assert (np.diff(by_wickets) <= 1e-9).all()
    assert by_runs[-1] - by_runs[0] > 0.3


def test_the_chase_equation_moves_the_right_way(
    model: WinProbabilityModel, table: chase.Table
) -> None:
    by_needed = wp(model, [chase_state(n, 36, 4, table) for n in range(1, 100, 3)])
    by_balls = wp(model, [chase_state(50, b, 4, table) for b in range(6, 120, 6)])
    by_wickets = wp(model, [chase_state(50, 36, w, table) for w in range(10)])
    assert (np.diff(by_needed) <= 1e-9).all()
    assert (np.diff(by_balls) >= -1e-9).all()
    assert (np.diff(by_wickets) <= 1e-9).all()


def test_endgame_extremes(model: WinProbabilityModel, table: chase.Table) -> None:
    easy, hopeless = wp(model, [chase_state(2, 18, 2, table), chase_state(30, 2, 8, table)])
    assert easy > 0.95
    assert hopeless < 0.02


def test_explanations_add_up_to_the_prediction(
    model: WinProbabilityModel, table: chase.Table
) -> None:
    for number, rows in (
        (1, [first_innings(r, 72, w) for r in (60, 110) for w in (1, 6)]),
        (2, [chase_state(n, 30, w, table) for n in (20, 60) for w in (2, 7)]),
    ):
        innings = model.innings[number]
        frame = pd.DataFrame(rows)
        p, points = innings.explain(frame)
        base = innings.base_probability()
        np.testing.assert_allclose(points.sum(axis=1), 100 * (p - base), atol=1e-6)
        np.testing.assert_allclose(p, innings.predict(frame))


def test_model_round_trips_through_the_registry_format(
    model: WinProbabilityModel, table: chase.Table, tmp_path: Path
) -> None:
    model.save(tmp_path)
    loaded = WinProbabilityModel.load(tmp_path)
    rows = [chase_state(40, 30, 3, table), chase_state(90, 60, 5, table)]
    np.testing.assert_allclose(wp(loaded, rows), wp(model, rows))
    assert loaded.version == model.version


def test_terminal_rules() -> None:
    def chase(runs: int, wickets: int, legal: int) -> float | None:
        return terminal_probability(
            innings_no=2, runs=runs, wickets=wickets, legal_balls=legal, max_balls=120, target=180
        )

    assert chase(180, 3, 110) == 1.0
    assert chase(170, 10, 110) == 0.0
    assert chase(179, 6, 120) == 0.5
    assert chase(150, 6, 100) is None
    assert (
        terminal_probability(
            innings_no=1, runs=0, wickets=0, legal_balls=0, max_balls=120, target=None
        )
        is None
    )


def test_platt_scaling_is_monotone() -> None:
    raw = np.linspace(-4, 4, 200)
    y = (np.random.default_rng(1).random(200) < 1 / (1 + np.exp(-raw))).astype(float)
    platt = Platt.fit(raw, y)
    assert platt.a > 0
    assert (np.diff(platt(raw)) > 0).all()
