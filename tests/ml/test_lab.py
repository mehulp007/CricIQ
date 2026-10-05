"""Analytics Lab research notes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from criciq_ml import lab


def _synthetic(slope: float, matches: int = 300, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for m in range(matches):
        shared = rng.normal(0, 1)  # balls in a match share conditions
        for _ in range(20):
            x = rng.normal(0, 10)
            rows.append((m, x, slope * x + shared + rng.normal(0, 3)))
    return pd.DataFrame(rows, columns=["match_id", "x", "y"])


def test_bootstrap_slope_recovers_the_truth() -> None:
    estimate, low, high = lab.bootstrap_slope(_synthetic(0.05), "x", "y", scale=10)
    assert estimate == pytest.approx(0.5, abs=0.15)
    assert low < estimate < high
    assert high - low < 0.5
    estimate, low, high = lab.bootstrap_slope(_synthetic(0.0), "x", "y")
    assert low < 0 < high


def test_bootstrap_mean_resamples_matches() -> None:
    frame = _synthetic(0.0)
    estimate, low, high = lab.bootstrap_mean(frame, "y")
    assert low < estimate < high
    # Balls in a match are correlated, so the interval is wider than treating them as independent.
    naive = 1.645 * frame["y"].std() / np.sqrt(len(frame))
    assert (high - low) / 2 > 1.5 * naive
    assert np.isnan(lab.bootstrap_mean(frame.iloc[0:0], "y")[0])


def test_notes_on_the_fixture_matches(fixture_scored_serving_db: Path, tmp_path: Path) -> None:
    written = lab.write_all(fixture_scored_serving_db, tmp_path)
    assert {p.name for p in written} == {"momentum.json", "pressure.json", "clutch.json"}
    momentum = json.loads((tmp_path / "momentum.json").read_text(encoding="utf-8"))
    assert momentum["states"] > 0
    assert [b["label"] for b in momentum["bands"]] == [b[0] for b in lab.MOMENTUM_BANDS]
    pressure = json.loads((tmp_path / "pressure.json").read_text(encoding="utf-8"))
    assert pressure["balls"] > 0
    assert sum(r["balls"] for r in pressure["rows"]) == pressure["balls"]
    assert pressure["top_moments"]
    top = pressure["top_moments"][0]
    assert top["leverage"] >= pressure["top_moments"][-1]["leverage"]
    clutch = json.loads((tmp_path / "clutch.json").read_text(encoding="utf-8"))
    assert set(clutch["roles"]) == {"batting", "bowling"}


def test_notes_need_pressure_scores(fixture_serving_db: Path, tmp_path: Path) -> None:
    assert lab.write_all(fixture_serving_db, tmp_path) == []


def test_bundled_notes_are_current() -> None:
    for slug in ("momentum", "pressure", "clutch"):
        note = json.loads((lab.LAB_DIR / f"{slug}.json").read_text(encoding="utf-8"))
        assert note["slug"] == slug
