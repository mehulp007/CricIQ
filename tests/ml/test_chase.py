"""The WASP-style chase dynamic programme."""

from pathlib import Path

import numpy as np
import pytest

from criciq_ml import chase
from criciq_ml.data import load_inputs


@pytest.fixture(scope="module")
def table() -> chase.Table:
    return chase.solve({low: chase.PRIOR for low, _ in chase.BUCKETS})


def test_finished_chases(table: chase.Table) -> None:
    assert chase.lookup(table, 0, 30, 5) == 1.0
    assert chase.lookup(table, 1, 0, 5) == 0.5  # scores level, no balls left: a tie
    assert chase.lookup(table, 2, 0, 5) == 0.0
    assert chase.lookup(table, 5, 12, 10) == 0.0  # all out


def test_impossible_and_near_certain(table: chase.Table) -> None:
    assert chase.lookup(table, 40, 1, 0) < 1e-3
    assert chase.lookup(table, 13, 1, 0) < 0.01
    assert chase.lookup(table, 1, 60, 0) > 0.99


def test_monotone_in_runs_balls_and_wickets(table: chase.Table) -> None:
    runs = np.array([chase.lookup(table, r, 24, 4) for r in range(1, 80)])
    balls = np.array([chase.lookup(table, 40, b, 4) for b in range(1, 120)])
    wickets = np.array([chase.lookup(table, 40, 24, w) for w in range(10)])
    assert (np.diff(runs) <= 1e-9).all()
    assert (np.diff(balls) >= -1e-9).all()
    assert (np.diff(wickets) <= 1e-9).all()


def test_outcome_rates_from_data_are_a_distribution(fixture_warehouse: Path) -> None:
    rates = chase.estimate_rates(load_inputs(fixture_warehouse).deliveries)
    for r in rates.values():
        total = r.extra + r.wicket + sum(r.runs.values())
        assert total == pytest.approx(1.0)
