"""Training protocol for the ball-outcome model and the head-to-head shrinkage.

1. Tune the player penalty: fit on seasons up to ``tune_train_through``,
   compare on ``tune_valid``. The same split decides whether phase-specific
   player effects earn their place.
2. Test once: refit up to the season before the test seasons with the chosen
   settings, and score the test seasons against a phase-and-wickets baseline
   and against the same model without players. Report per-outcome calibration.
3. Backtest: for each season from ``backtest_from``, fit on every earlier
   season and score that season.
4. Head-to-head: estimate how many balls of prior evidence a pair's history
   is worth (``kappa``) from the training seasons, then check on the test
   seasons whether shrunk head-to-head records predict better than the model
   alone and than raw head-to-head rates.
5. Serve: refit on every season and refit ``kappa``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

from criciq_core import paths
from criciq_ml.ball_outcome import (
    CLASSES,
    PHASES,
    RUNS,
    BallOutcomeModel,
    FloatArray,
    MarginalBaseline,
    brier,
    fit_kappa,
    log_loss,
    pair_counts,
)

Log = Callable[[str], None]

# A candidate joins the served model only if it cuts validation log loss by at
# least this share: single balls are noisy, and every extra term is served.
CANDIDATE_MIN_GAIN = 0.001


def _quiet(_: str) -> None:
    pass


class Splits(BaseModel):
    tune_train_through: int
    tune_valid: list[int]
    test: list[int]
    backtest_from: int


class ModelSettings(BaseModel):
    c: float
    max_iter: int
    player_scale_grid: list[float]


class BallOutcomeConfig(BaseModel):
    name: str
    version: str
    splits: Splits
    model: ModelSettings
    gate: dict[str, Any]


def load_ball_outcome_config(path: Path | None = None) -> BallOutcomeConfig:
    source = path or paths.config_dir() / "models" / "ball_outcome.yaml"
    with source.open(encoding="utf-8") as fh:
        return BallOutcomeConfig.model_validate(yaml.safe_load(fh))


# --------------------------------------------------------------------------- metrics


def metrics(probs: FloatArray, balls: pd.DataFrame) -> dict[str, Any]:
    y = balls["outcome"].to_numpy()
    return {
        "balls": len(balls),
        "log_loss": log_loss(probs, y),
        "brier": brier(probs, y),
        "expected_runs": float((probs @ RUNS).mean()),
        "actual_runs": float(RUNS[y].mean()),
    }


def class_calibration(probs: FloatArray, balls: pd.DataFrame, bins: int = 10) -> dict[str, Any]:
    """Per outcome: predicted vs observed rate overall and in predicted-probability deciles."""
    y = balls["outcome"].to_numpy()
    out: dict[str, Any] = {}
    for k, name in enumerate(CLASSES):
        p = probs[:, k]
        hit = (y == k).astype(float)
        edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
        which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
        rows = []
        ece = 0.0
        for b in range(len(edges) - 1):
            mask = which == b
            if not mask.any():
                continue
            predicted, observed = float(p[mask].mean()), float(hit[mask].mean())
            ece += mask.mean() * abs(predicted - observed)
            rows.append({"predicted": predicted, "observed": observed, "count": int(mask.sum())})
        out[name] = {
            "predicted": float(p.mean()),
            "observed": float(hit.mean()),
            "ece": float(ece),
            "bins": rows,
        }
    return out


def runs_calibration(
    probs: FloatArray, balls: pd.DataFrame, bins: int = 10
) -> list[dict[str, Any]]:
    expected = probs @ RUNS
    actual = RUNS[balls["outcome"].to_numpy()]
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    which = np.clip(np.searchsorted(edges, expected, side="right") - 1, 0, bins - 1)
    return [
        {
            "predicted": float(expected[which == b].mean()),
            "observed": float(actual[which == b].mean()),
            "count": int((which == b).sum()),
        }
        for b in range(bins)
        if (which == b).any()
    ]


# --------------------------------------------------------------------------- protocol


def _fit(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, scale: float, phase_players: bool = False
) -> BallOutcomeModel:
    return BallOutcomeModel.fit(
        balls,
        player_scale=scale,
        c=cfg.model.c,
        max_iter=cfg.model.max_iter,
        phase_players=phase_players,
    )


def _tune(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, log: Log
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    s = cfg.splits
    train = balls[balls["season"] <= s.tune_train_through]
    valid = balls[balls["season"].isin(s.tune_valid)]
    grid = []
    for scale in cfg.model.player_scale_grid:
        loss = log_loss(_fit(train, cfg, scale).predict(valid), valid["outcome"])
        grid.append({"player_scale": scale, "log_loss": loss})
        log(f"    player scale {scale}: valid log loss {loss:.5f}")
    best = min(grid, key=lambda r: r["log_loss"])
    scale = float(best["player_scale"])

    recent = train[train["season"] >= s.tune_train_through - 1]
    selection = [
        {
            "variant": "baseline",
            "label": "Phase and wickets only",
            "log_loss": log_loss(MarginalBaseline(recent).predict(valid), valid["outcome"]),
        },
        {
            "variant": "situation",
            "label": "Match situation, no players",
            "log_loss": log_loss(_fit(train, cfg, 1e-6).predict(valid), valid["outcome"]),
        },
        {"variant": "served", "label": "+ batter and bowler", "log_loss": best["log_loss"]},
        {
            "variant": "phase_players",
            "label": "+ separate player effects per phase",
            "log_loss": log_loss(
                _fit(train, cfg, scale, phase_players=True).predict(valid), valid["outcome"]
            ),
        },
    ]
    for row in selection:
        log(f"    {row['label']}: {row['log_loss']:.5f}")
    return scale, grid, selection


def _matchup_validation(
    model: BallOutcomeModel, train: pd.DataFrame, test: pd.DataFrame
) -> dict[str, Any]:
    """Do head-to-head records predict a pair's future balls better than the model?"""
    history = pair_counts(train, model.predict(train))
    n = history[[f"n_{c}" for c in CLASSES]].to_numpy()
    e = history[[f"e_{c}" for c in CLASSES]].to_numpy()
    totals = n.sum(axis=1, keepdims=True)
    q = e / totals
    kappa = fit_kappa(n, q)
    posterior = (n + kappa * q) / (totals + kappa)
    ratio = pd.DataFrame(posterior / q, index=history.index)
    raw = pd.DataFrame((n + 0.5) / (totals + 0.5 * len(CLASSES)), index=history.index)
    sizes = pd.Series(totals[:, 0], index=history.index)

    keys = pd.MultiIndex.from_frame(test[["batter_id", "bowler_id"]])
    seen = keys.isin(history.index)
    met = test[seen]
    met_keys = keys[seen]
    p_model = model.predict(met)
    shrunk = p_model * ratio.reindex(met_keys).to_numpy()
    shrunk /= shrunk.sum(axis=1, keepdims=True)
    p_raw = raw.reindex(met_keys).to_numpy()
    y = met["outcome"].to_numpy()
    size = sizes.reindex(met_keys).to_numpy()

    def score(mask: np.ndarray) -> dict[str, Any]:
        return {
            "balls": int(mask.sum()),
            "model": log_loss(p_model[mask], y[mask]),
            "shrunk": log_loss(shrunk[mask], y[mask]),
            "raw": log_loss(p_raw[mask], y[mask]),
        }

    buckets = []
    for low, high, label in ((1, 10, "1-9"), (10, 30, "10-29"), (30, 10_000, "30+")):
        mask = (size >= low) & (size < high)
        if mask.any():
            buckets.append({"history": label, **score(mask)})
    return {
        "kappa": kappa,
        "pairs_in_history": len(history),
        "test_pairs": int(pd.Index(met_keys).nunique()),
        "all": score(np.ones(len(met), dtype=bool)),
        "by_history": buckets,
    }


def _backtest(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, scale: float, phase_players: bool, log: Log
) -> list[dict[str, Any]]:
    rows = []
    for season in sorted(balls["season"].unique()):
        if season < cfg.splits.backtest_from:
            continue
        train = balls[balls["season"] < season]
        test = balls[balls["season"] == season]
        model = _fit(train, cfg, scale, phase_players)
        baseline = MarginalBaseline(train[train["season"] >= season - 2])
        row = {
            "season": int(season),
            "balls": len(test),
            "model_log_loss": log_loss(model.predict(test), test["outcome"]),
            "baseline_log_loss": log_loss(baseline.predict(test), test["outcome"]),
        }
        rows.append(row)
        log(
            f"    {season}: model {row['model_log_loss']:.4f} "
            f"baseline {row['baseline_log_loss']:.4f}"
        )
    return rows


def served_kappa(model: BallOutcomeModel, balls: pd.DataFrame) -> float:
    history = pair_counts(balls, model.predict(balls))
    n = history[[f"n_{c}" for c in CLASSES]].to_numpy()
    e = history[[f"e_{c}" for c in CLASSES]].to_numpy()
    return fit_kappa(n, e / n.sum(axis=1, keepdims=True))


def train_ball_outcome(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, *, data_version: str, log: Log = _quiet
) -> tuple[BallOutcomeModel, dict[str, Any]]:
    s = cfg.splits
    log("  tuning the player penalty")
    scale, grid, selection = _tune(balls, cfg, log)
    loss = {r["variant"]: r["log_loss"] for r in selection}
    phase_players = (loss["served"] - loss["phase_players"]) / loss["served"] >= CANDIDATE_MIN_GAIN
    log(f"    separate per-phase player effects: {'kept' if phase_players else 'not kept'}")

    log("  test seasons")
    train = balls[balls["season"] < min(s.test)]
    test = balls[balls["season"].isin(s.test)]
    model = _fit(train, cfg, scale, phase_players)
    p_model = model.predict(test)
    p_situation = _fit(train, cfg, 1e-6).predict(test)
    baseline = MarginalBaseline(train[train["season"] >= min(s.test) - 2])
    p_base = baseline.predict(test)
    by_phase = []
    for phase in PHASES:
        mask = (test["phase"] == phase).to_numpy()
        by_phase.append(
            {
                "phase": phase,
                "balls": int(mask.sum()),
                "model_log_loss": log_loss(p_model[mask], test["outcome"].to_numpy()[mask]),
                "baseline_log_loss": log_loss(p_base[mask], test["outcome"].to_numpy()[mask]),
            }
        )
    test_report: dict[str, Any] = {
        "model": metrics(p_model, test),
        "situation_only": metrics(p_situation, test),
        "baseline": metrics(p_base, test),
        "by_phase": by_phase,
        "calibration": class_calibration(p_model, test),
        "runs_calibration": runs_calibration(p_model, test),
    }
    log(
        f"    log loss {test_report['model']['log_loss']:.5f} "
        f"(situation {test_report['situation_only']['log_loss']:.5f}, "
        f"baseline {test_report['baseline']['log_loss']:.5f})"
    )

    log("  head-to-head shrinkage")
    matchups = _matchup_validation(model, train, test)
    log(
        f"    kappa {matchups['kappa']:.0f} balls; future log loss model "
        f"{matchups['all']['model']:.4f}, shrunk {matchups['all']['shrunk']:.4f}, "
        f"raw {matchups['all']['raw']:.4f}"
    )

    log("  backtest")
    backtest = _backtest(balls, cfg, scale, phase_players, log)

    log("  serving fit")
    seasons = [int(balls["season"].min()), int(balls["season"].max())]
    served = _fit(balls, cfg, scale, phase_players)
    kappa = served_kappa(served, balls)
    served.manifest.update(
        {
            "name": cfg.name,
            "version": cfg.version,
            "data_version": data_version,
            "kappa": kappa,
            "trained_on": {"seasons": seasons, "balls": len(balls)},
        }
    )
    log(f"    served kappa {kappa:.0f} balls")
    evaluation = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "classes": list(CLASSES),
        "splits": {
            "tune_train_through": s.tune_train_through,
            "tune_valid": s.tune_valid,
            "test": s.test,
            "served_through": seasons[1],
        },
        "trained_on": {"seasons": seasons, "balls": len(balls)},
        "tuning": {
            "player_scale": scale,
            "grid": grid,
            "candidate_min_gain": CANDIDATE_MIN_GAIN,
            "phase_players": phase_players,
        },
        "feature_selection": selection,
        "test": test_report,
        "matchups": {**matchups, "served_kappa": kappa},
        "backtest": backtest,
    }
    return served, evaluation


def gate(evaluation: dict[str, Any]) -> list[str]:
    test = evaluation["test"]
    problems = []
    if test["model"]["log_loss"] >= test["baseline"]["log_loss"]:
        problems.append("does not beat the phase-and-wickets baseline on test log loss")
    return problems
