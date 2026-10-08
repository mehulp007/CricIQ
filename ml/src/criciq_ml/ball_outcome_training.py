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

The fits within a step are independent (grid points, the test fits, every
backtest season), so they run in parallel processes (``n_jobs``); each fit is
deterministic, so the results do not depend on how many run at once.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from joblib import Parallel, delayed
from pydantic import BaseModel

from criciq_core.phases import model_format, use_format
from criciq_ml import formats
from criciq_ml.ball_outcome import (
    CLASSES,
    RUNS,
    BallOutcomeModel,
    FloatArray,
    MarginalBaseline,
    brier,
    fit_kappa,
    log_loss,
    pair_counts,
    phases,
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
    # One term per competition (a model fitted on several).
    competition_terms: bool = False
    # One term per national side on international balls (players shrink towards it).
    side_terms: bool = False
    # Independent fits run in this many processes at once.
    n_jobs: int = 1


class BallOutcomeConfig(BaseModel):
    name: str
    version: str
    # The warehouse copy trained on: a competition ("IPL") or the pooled T20 copy ("T20").
    scope: str = "IPL"
    splits: Splits
    model: ModelSettings
    gate: dict[str, Any]


def load_ball_outcome_config(path: Path | None = None) -> BallOutcomeConfig:
    source = path or formats.config_path("ball_outcome")
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
        competition_terms=cfg.model.competition_terms,
        side_terms=cfg.model.side_terms,
    )


def _fit_in(
    match_format: str, balls: pd.DataFrame, cfg: BallOutcomeConfig, scale: float, phase: bool
) -> BallOutcomeModel:
    """``_fit`` in a worker process, which starts in the default format."""
    with use_format(match_format):
        return _fit(balls, cfg, scale, phase)


def _fit_many(
    jobs: list[tuple[pd.DataFrame, float, bool]], cfg: BallOutcomeConfig
) -> list[BallOutcomeModel]:
    """Fit (balls, player scale, phase players) jobs, in parallel processes."""
    if cfg.model.n_jobs <= 1 or len(jobs) == 1:
        return [_fit(balls, cfg, scale, phase) for balls, scale, phase in jobs]
    match_format = model_format()
    models: list[BallOutcomeModel] = Parallel(
        n_jobs=min(cfg.model.n_jobs, len(jobs)), backend="loky"
    )(delayed(_fit_in)(match_format, balls, cfg, scale, phase) for balls, scale, phase in jobs)
    return models


def _tune(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, log: Log
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    s = cfg.splits
    train = balls[balls["season"] <= s.tune_train_through]
    valid = balls[balls["season"].isin(s.tune_valid)]
    scales = cfg.model.player_scale_grid
    *fitted, situation = _fit_many(
        [(train, scale, False) for scale in scales] + [(train, 1e-6, False)], cfg
    )
    grid = []
    for scale, model in zip(scales, fitted, strict=True):
        loss = log_loss(model.predict(valid), valid["outcome"])
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
            "log_loss": log_loss(situation.predict(valid), valid["outcome"]),
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
    seasons = [s for s in sorted(balls["season"].unique()) if s >= cfg.splits.backtest_from]
    models = _fit_many(
        [(balls[balls["season"] < season], scale, phase_players) for season in seasons], cfg
    )
    for season, model in zip(seasons, models, strict=True):
        train = balls[balls["season"] < season]
        test = balls[balls["season"] == season]
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


def by_competition(
    p_model: FloatArray, p_base: FloatArray, test: pd.DataFrame
) -> list[dict[str, Any]]:
    """Test metrics in each competition (pooled models), against the baseline."""
    if "competition_id" not in test or test["competition_id"].nunique() < 2:
        return []
    competitions = test["competition_id"].to_numpy()
    return [
        {
            "competition": str(competition),
            "model": metrics(p_model[mask], test[mask]),
            "baseline": metrics(p_base[mask], test[mask]),
        }
        for competition in sorted(set(competitions))
        if (mask := competitions == competition).any()
    ]


def train_ball_outcome(
    balls: pd.DataFrame, cfg: BallOutcomeConfig, *, data_version: str, log: Log = _quiet
) -> tuple[BallOutcomeModel, dict[str, Any], pd.DataFrame]:
    """Model, evaluation, and the headline model's test probabilities ball by ball."""
    s = cfg.splits
    log("  tuning the player penalty")
    scale, grid, selection = _tune(balls, cfg, log)
    loss = {r["variant"]: r["log_loss"] for r in selection}
    phase_players = (loss["served"] - loss["phase_players"]) / loss["served"] >= CANDIDATE_MIN_GAIN
    log(f"    separate per-phase player effects: {'kept' if phase_players else 'not kept'}")

    log("  test seasons")
    train = balls[balls["season"] < min(s.test)]
    test = balls[balls["season"].isin(s.test)]
    model, situation = _fit_many([(train, scale, phase_players), (train, 1e-6, False)], cfg)
    p_model = model.predict(test)
    p_situation = situation.predict(test)
    baseline = MarginalBaseline(train[train["season"] >= min(s.test) - 2])
    p_base = baseline.predict(test)
    by_phase = []
    for phase in phases():
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
        "by_competition": by_competition(p_model, p_base, test),
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
            "trained_on": {
                "seasons": seasons,
                "balls": len(balls),
                # Listed unless the IPL alone (v1's manifest), so scoring finds the
                # copy the model was fitted on (the pooled one, or the ODIs').
                **(
                    {"competitions": sorted(balls["competition_id"].unique().tolist())}
                    if set(balls["competition_id"].unique()) != {"IPL"}
                    else {}
                ),
            },
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
    keys = [c for c in ("match_id", "innings_no", "seq_no", "competition_id") if c in test]
    predictions = test[[*keys, "outcome"]].assign(probs=list(p_model))
    return served, evaluation, predictions


def gate(evaluation: dict[str, Any]) -> list[str]:
    test = evaluation["test"]
    problems = []
    if test["model"]["log_loss"] >= test["baseline"]["log_loss"]:
        problems.append("does not beat the phase-and-wickets baseline on test log loss")
    for line in test.get("by_competition", []):
        if line["model"]["log_loss"] >= line["baseline"]["log_loss"]:
            problems.append(f"does not beat the baseline on {line['competition']} test log loss")
    return problems
