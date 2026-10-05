"""Train, evaluate and backtest the first-innings score projection.

1. **Tune** each grid candidate on seasons up to ``tune_train_through`` with
   early stopping on ``tune_valid`` (pinball loss, averaged over levels).
2. **Headline:** fit on seasons before the calibration pair, calibrate on it
   (conformal shifts per level), score the **test** seasons once. Compare with
   two baselines: a TV-style run-rate projection (point only) and "par for the
   era plus the historical spread" (a full distribution, calibrated the same way).
3. **Feature selection** and a season-by-season **backtest** by rolling origin.
   Feature selection never looks at the test seasons.
4. Fit the **served model** on every season. Its shifts come from out-of-fold
   predictions for the two most recent seasons.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

from criciq_core.paths import config_dir
from criciq_core.phases import default_phase_config
from criciq_ml.projection import (
    CANDIDATES,
    FEATURES,
    HIGH80,
    LEVELS,
    LOW80,
    MEDIAN,
    TARGET,
    FloatArray,
    ScoreProjectionModel,
    conformal_shifts,
    fit_quantiles,
    probability_at_least,
    projection_frame,
    raw_ratios,
    to_totals,
    trainable,
)

Log = Callable[[str], None]


def _quiet(_: str) -> None:
    return None


# ---------------------------------------------------------------- config


class Splits(BaseModel):
    tune_train_through: int
    tune_valid: list[int]
    calibrate: list[int]
    test: list[int]
    backtest_from: int


class ProjectionConfig(BaseModel):
    name: str
    version: str
    splits: Splits
    lightgbm: dict[str, dict[str, Any]]
    thresholds: list[int]
    gate: dict[str, list[float]]

    def candidates(self) -> list[dict[str, Any]]:
        grid = self.lightgbm["grid"]
        keys = list(grid)
        combos: list[dict[str, Any]] = [{}]
        for key in keys:
            combos = [{**c, key: v} for c in combos for v in grid[key]]
        return combos


def load_projection_config(path: Path | None = None) -> ProjectionConfig:
    source = path or config_dir() / "models" / "score_projection.yaml"
    with source.open(encoding="utf-8") as fh:
        return ProjectionConfig.model_validate(yaml.safe_load(fh))


# ---------------------------------------------------------------- metrics


def pinball(quantiles: FloatArray, y: FloatArray) -> float:
    """Pinball loss in runs, averaged over levels (an estimate of CRPS / 2)."""
    losses = [
        np.mean(np.maximum(level * (y - quantiles[:, i]), (level - 1) * (y - quantiles[:, i])))
        for i, level in enumerate(LEVELS)
    ]
    return float(np.mean(losses))


def summarize(quantiles: FloatArray, frame: pd.DataFrame, thresholds: list[int]) -> dict[str, Any]:
    y = frame["final_runs"].to_numpy(dtype=np.float64)
    current = frame["runs"].to_numpy(dtype=np.float64)
    median = quantiles[:, MEDIAN]
    inside = (y >= quantiles[:, LOW80]) & (y <= quantiles[:, HIGH80])
    briers = []
    for threshold in thresholds:
        p = probability_at_least(quantiles, current, threshold)
        briers.append(float(np.mean((p - (y >= threshold)) ** 2)))
    return {
        "rows": len(y),
        "innings": int(frame["match_id"].nunique()),
        "coverage80": float(inside.mean()),
        "width80": float(np.mean(quantiles[:, HIGH80] - quantiles[:, LOW80])),
        "mae": float(np.mean(np.abs(median - y))),
        "bias": float(np.mean(median - y)),
        "pinball": pinball(quantiles, y),
        "threshold_brier": float(np.mean(briers)),
        "level_calibration": [
            {"level": level, "observed": float(np.mean(y <= quantiles[:, i]))}
            for i, level in enumerate(LEVELS)
        ],
    }


def point_summary(point: FloatArray, frame: pd.DataFrame) -> dict[str, Any]:
    y = frame["final_runs"].to_numpy(dtype=np.float64)
    return {
        "rows": len(y),
        "mae": float(np.mean(np.abs(point - y))),
        "bias": float(np.mean(point - y)),
    }


# ---------------------------------------------------------------- baselines


def run_rate_projection(frame: pd.DataFrame) -> FloatArray:
    """The TV graphic: current run rate carried to the end (par before the first ball)."""
    legal = frame["legal_balls"].to_numpy(dtype=np.float64)
    runs = frame["runs"].to_numpy(dtype=np.float64)
    par = runs + frame["expected_rest"].to_numpy(dtype=np.float64)
    rate = np.divide(runs, legal, out=np.zeros_like(runs), where=legal > 0)
    left = frame["balls_remaining"].to_numpy(dtype=np.float64)
    return np.asarray(np.where(legal > 0, runs + rate * left, par), dtype=np.float64)


BUCKETS = [0, 30, 60, 90, 121]


class ParBaseline:
    """Par for the era, spread by how that ratio historically varied at this stage."""

    def __init__(self, calibration: pd.DataFrame) -> None:
        bucket = pd.cut(calibration["balls_remaining"], BUCKETS, right=True)
        self.table = {
            interval: np.quantile(group[TARGET].to_numpy(), LEVELS)
            for interval, group in calibration.groupby(bucket, observed=True)
        }

    def predict(self, frame: pd.DataFrame) -> FloatArray:
        bucket = pd.cut(frame["balls_remaining"], BUCKETS, right=True)
        ratios = np.vstack([self.table[b] for b in bucket])
        return to_totals(ratios, frame)


# ---------------------------------------------------------------- protocol


def _fit_and_calibrate(
    cfg: ProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: dict[float, int],
    features: list[str],
    *,
    before: int,
) -> tuple[Any, FloatArray]:
    """Fit on seasons before ``before - 2``, calibrate on the two seasons after."""
    train = data[data["season"] < before - 2]
    calibrate = data[data["season"].isin([before - 2, before - 1])]
    boosters, _ = fit_quantiles(
        cfg.lightgbm["base"], choice, train, features=features, rounds=rounds
    )
    shifts = conformal_shifts(
        raw_ratios(boosters, calibrate, features), calibrate[TARGET].to_numpy()
    )
    return boosters, shifts


def _tune(
    cfg: ProjectionConfig, data: pd.DataFrame, log: Log
) -> tuple[dict[str, Any], dict[float, int], list[dict[str, Any]]]:
    train = data[data["season"] <= cfg.splits.tune_train_through]
    valid = data[data["season"].isin(cfg.splits.tune_valid)]
    y = valid["final_runs"].to_numpy(dtype=np.float64)
    table = []
    best: tuple[float, dict[str, Any], dict[float, int]] | None = None
    for choice in cfg.candidates():
        boosters, rounds = fit_quantiles(
            cfg.lightgbm["base"], choice, train, features=FEATURES, valid=valid
        )
        loss = pinball(to_totals(raw_ratios(boosters, valid, FEATURES), valid), y)
        table.append(
            {**choice, "rounds": {str(k): v for k, v in rounds.items()}, "valid_pinball": loss}
        )
        log(f"    {choice} -> pinball {loss:.3f}")
        if best is None or loss < best[0]:
            best = (loss, choice, rounds)
    assert best is not None
    return best[1], best[2], table


def _phase(frame: pd.DataFrame) -> np.ndarray:
    phases = default_phase_config().for_format("T20")
    overs = (frame["legal_balls"].clip(lower=0) // phases.balls_per_over).clip(
        upper=phases.limit - 1
    )
    return np.asarray(overs.map(lambda o: phases.phase_for_over_index(int(o)).key).to_numpy())


def train_projection(
    states: pd.DataFrame, cfg: ProjectionConfig, *, data_version: str, log: Log = _quiet
) -> tuple[ScoreProjectionModel, dict[str, Any]]:
    started = time.perf_counter()
    frame = projection_frame(states)
    data = trainable(frame)
    first_test = min(cfg.splits.test)
    test = data[data["season"].isin(cfg.splits.test)]

    log("> tuning")
    choice, rounds, grid = _tune(cfg, data, log)

    log("> scoring the test seasons")
    boosters, shifts = _fit_and_calibrate(cfg, data, choice, rounds, FEATURES, before=first_test)
    q_model = to_totals(raw_ratios(boosters, test, FEATURES), test, shifts)
    q_uncal = to_totals(raw_ratios(boosters, test, FEATURES), test)
    calibration = data[data["season"].isin([first_test - 2, first_test - 1])]
    q_par = ParBaseline(calibration).predict(test)
    rr = run_rate_projection(test)

    phases = _phase(test)
    by_phase = []
    for phase in ("powerplay", "middle", "death"):
        mask = phases == phase
        m = summarize(q_model[mask], test[mask], cfg.thresholds)
        b = summarize(q_par[mask], test[mask], cfg.thresholds)
        by_phase.append(
            {
                "phase": phase,
                "rows": int(mask.sum()),
                "model_mae": m["mae"],
                "par_mae": b["mae"],
                "run_rate_mae": point_summary(rr[mask], test[mask])["mae"],
                "model_coverage80": m["coverage80"],
                "model_width80": m["width80"],
            }
        )

    log("> feature selection (rolling origin, pre-test seasons)")
    selection = _feature_selection(cfg, data, choice, rounds, log)

    log("> rolling-origin backtest")
    backtest = _backtest(cfg, data, choice, rounds, log)

    log("> fitting the served model on every season")
    model = _fit_served(cfg, data, choice, rounds, log)

    evaluation: dict[str, Any] = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "splits": cfg.splits.model_dump() | {"served_through": int(data["season"].max())},
        "test": {
            "model": summarize(q_model, test, cfg.thresholds),
            "uncalibrated": summarize(q_uncal, test, cfg.thresholds),
            "par_baseline": summarize(q_par, test, cfg.thresholds),
            "run_rate": point_summary(rr, test),
            "by_phase": by_phase,
            "thresholds": cfg.thresholds,
        },
        "feature_selection": selection,
        "backtest": backtest,
        "tuning": {
            "chosen": choice,
            "rounds": {str(k): v for k, v in rounds.items()},
            "grid": grid,
        },
        "training_seconds": round(time.perf_counter() - started, 1),
    }
    model.manifest["headline"] = {
        "test_coverage80": evaluation["test"]["model"]["coverage80"],
        "test_mae": evaluation["test"]["model"]["mae"],
    }
    return model, evaluation


def _rolling_quantiles(
    cfg: ProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: dict[float, int],
    features: list[str],
    season: int,
) -> tuple[pd.DataFrame, FloatArray]:
    boosters, shifts = _fit_and_calibrate(cfg, data, choice, rounds, features, before=season)
    target = data[data["season"] == season]
    return target, to_totals(raw_ratios(boosters, target, features), target, shifts)


def _feature_selection(
    cfg: ProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: dict[float, int],
    log: Log,
) -> list[dict[str, Any]]:
    seasons = [
        int(s)
        for s in sorted(data["season"].unique())
        if cfg.splits.backtest_from <= s < min(cfg.splits.test)
    ]
    table = []
    variants = {"served": FEATURES} | {f"+{k}": FEATURES + v for k, v in CANDIDATES.items()}
    for name, features in variants.items():
        frames, quantiles = [], []
        for season in seasons:
            frame, q = _rolling_quantiles(cfg, data, choice, rounds, features, season)
            frames.append(frame)
            quantiles.append(q)
        all_frames, all_q = pd.concat(frames), np.vstack(quantiles)
        y = all_frames["final_runs"].to_numpy(dtype=np.float64)
        row = {
            "variant": name,
            "features": features,
            "pinball": pinball(all_q, y),
            "mae": float(np.mean(np.abs(all_q[:, MEDIAN] - y))),
            "seasons": [seasons[0], seasons[-1]],
        }
        log(f"    {name:10} pinball {row['pinball']:.3f}  MAE {row['mae']:.2f}")
        table.append(row)
    return table


def _backtest(
    cfg: ProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: dict[float, int],
    log: Log,
) -> list[dict[str, Any]]:
    table = []
    for season in sorted(int(s) for s in data["season"].unique() if s >= cfg.splits.backtest_from):
        frame, q = _rolling_quantiles(cfg, data, choice, rounds, FEATURES, season)
        m = summarize(q, frame, cfg.thresholds)
        par = ParBaseline(data[data["season"].isin([season - 2, season - 1])]).predict(frame)
        row = {
            "season": season,
            "innings": m["innings"],
            "coverage80": m["coverage80"],
            "mae": m["mae"],
            "bias": m["bias"],
            "par_mae": float(np.mean(np.abs(par[:, MEDIAN] - frame["final_runs"].to_numpy()))),
            "mean_total": float(frame.groupby("match_id")["final_runs"].first().mean()),
        }
        log(
            f"    {season}: coverage {row['coverage80']:.3f}, MAE {row['mae']:.2f} "
            f"(par {row['par_mae']:.2f}), bias {row['bias']:+.2f}"
        )
        table.append(row)
    return table


def _fit_served(
    cfg: ProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: dict[float, int],
    log: Log,
) -> ScoreProjectionModel:
    seasons = sorted(int(s) for s in data["season"].unique())
    recent = seasons[-2:]
    raws, targets = [], []
    for season in recent:
        boosters, _ = fit_quantiles(
            cfg.lightgbm["base"],
            choice,
            data[data["season"] != season],
            features=FEATURES,
            rounds=rounds,
        )
        held = data[data["season"] == season]
        raws.append(raw_ratios(boosters, held, FEATURES))
        targets.append(held[TARGET].to_numpy())
    shifts = conformal_shifts(np.vstack(raws), np.concatenate(targets))
    boosters, _ = fit_quantiles(
        cfg.lightgbm["base"], choice, data, features=FEATURES, rounds=rounds
    )
    log(f"    shifts {np.round(shifts, 3).tolist()}")
    manifest = {
        "name": cfg.name,
        "features": FEATURES,
        "params": choice,
        "rounds": {str(k): v for k, v in rounds.items()},
        "calibrated_on": recent,
        "trained_on": {
            "seasons": [seasons[0], seasons[-1]],
            "innings": int(data["match_id"].nunique()),
            "rows": len(data),
        },
        "lightgbm": package_version("lightgbm"),
    }
    return ScoreProjectionModel(
        version=cfg.version, boosters=boosters, shifts=shifts, manifest=manifest
    )
