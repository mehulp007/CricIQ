"""Train, tune, evaluate and backtest the win probability model.

The protocol (docs/model-cards/win-probability.md) in one place:

1. **Tune** on the validation seasons: each grid candidate is fit on seasons up
   to ``train_through`` with early stopping on validation.
2. **Choose calibration** (none or Platt scaling) with a rolling origin over the
   pre-test seasons.
3. Score the **test** seasons exactly once. Compare against a logistic
   regression on the match state and a state-only boosted model (ablation).
4. **Feature selection** and a season-by-season **backtest**, both with the
   rolling origin. Feature selection never looks at the test seasons.
5. Fit the **served model** on every season with the chosen settings.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from importlib.metadata import version as package_version
from typing import Any, Literal, cast

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from criciq_core.phases import model_phases
from criciq_ml import metrics
from criciq_ml.config import WinProbabilityConfig
from criciq_ml.features import CANDIDATES, LABEL, MONOTONE, STATE_FEATURES, group_keys
from criciq_ml.model import InningsModel, Platt, WinProbabilityModel, sigmoid

Log = Callable[[str], None]


def _quiet(_: str) -> None:
    return None


# ---------------------------------------------------------------- data helpers


def trainable(states: pd.DataFrame) -> pd.DataFrame:
    """Rows with a known result (no-result matches are never trained on)."""
    return states[states[LABEL].notna()]


def evaluable(states: pd.DataFrame) -> pd.DataFrame:
    """Rows worth scoring a model on: drop the final ball of a finished chase.

    Once a chase is over the served probability comes from the rule layer, not
    the model, so those rows would only flatter the metrics.
    """
    last = states.groupby(["match_id", "innings_no"])["seq_no"].transform("max")
    final = (states["innings_no"] == 2) & (states["seq_no"] == last)
    return states[~final]


def _seasons(states: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    return states[states["season"].isin(seasons)]


def _upto(states: pd.DataFrame, season: int) -> pd.DataFrame:
    return states[states["season"] <= season]


def phase_of(legal_balls: pd.Series) -> pd.Series:
    phases = model_phases()
    over_index = (legal_balls.clip(lower=0) // phases.balls_per_over).clip(upper=phases.limit - 1)
    return over_index.map(lambda o: phases.phase_for_over_index(int(o)).key)


# ---------------------------------------------------------------- model fitting


def _weights(states: pd.DataFrame, half_life: float) -> np.ndarray | None:
    if not half_life:
        return None
    latest = int(states["season"].max())
    return np.asarray(0.5 ** ((latest - states["season"]) / half_life), dtype=np.float64)


def _params(
    cfg: WinProbabilityConfig, innings_no: int, choice: dict[str, Any], features: list[str]
) -> dict[str, Any]:
    base = {
        k: v
        for k, v in cfg.lightgbm.base.items()
        if k not in {"max_rounds", "early_stopping_rounds", "num_threads"}
    }
    tree = {k: v for k, v in choice.items() if k != "recency_half_life"}
    monotone = MONOTONE[innings_no]
    return {
        **base,
        **tree,
        "monotone_constraints": [monotone.get(f, 0) for f in features],
        "deterministic": True,
        "force_row_wise": True,
        # Results are reproducible for a given thread count (v1 used 4).
        "num_threads": int(cfg.lightgbm.base.get("num_threads", 4)),
        "verbosity": -1,
    }


@dataclass
class Fitted:
    booster: lgb.Booster
    rounds: int


def fit_booster(
    cfg: WinProbabilityConfig,
    train: pd.DataFrame,
    innings_no: int,
    choice: dict[str, Any],
    *,
    features: list[str] | None = None,
    valid: pd.DataFrame | None = None,
    rounds: int | None = None,
) -> Fitted:
    features = features or cfg.served_features()[innings_no]
    params = _params(cfg, innings_no, choice, features)
    data = lgb.Dataset(
        train[features].to_numpy(dtype=np.float64),
        label=train[LABEL].to_numpy(),
        weight=_weights(train, choice.get("recency_half_life", 0)),
        feature_name=features,
        free_raw_data=False,
    )
    if valid is not None and rounds is None:
        vdata = data.create_valid(
            valid[features].to_numpy(dtype=np.float64), label=valid[LABEL].to_numpy()
        )
        booster = lgb.train(
            params,
            data,
            num_boost_round=int(cfg.lightgbm.base["max_rounds"]),
            valid_sets=[vdata],
            callbacks=[
                lgb.early_stopping(int(cfg.lightgbm.base["early_stopping_rounds"]), verbose=False)
            ],
        )
        best = booster.best_iteration or booster.current_iteration()
        return Fitted(booster, best)
    booster = lgb.train(params, data, num_boost_round=rounds or 200)
    return Fitted(booster, booster.current_iteration())


def raw_logit(fitted: Fitted, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.asarray(
        fitted.booster.predict(
            frame[features].to_numpy(dtype=np.float64),
            raw_score=True,
            num_iteration=fitted.rounds,
        ),
        dtype=np.float64,
    )


# ---------------------------------------------------------------- baseline


def _baseline_matrix(frame: pd.DataFrame, innings_no: int) -> np.ndarray:
    """A strong, classical baseline: logistic regression on the match state."""
    legal = frame["legal_balls"].to_numpy(dtype=float)
    wickets = frame["wickets"].to_numpy(dtype=float)
    if innings_no == 1:
        runs = frame["runs"].to_numpy(dtype=float)
        cols = [runs, wickets, legal, runs * 6 / np.maximum(legal, 1), wickets * legal / 120]
    else:
        needed = frame["runs_needed"].to_numpy(dtype=float)
        left = frame["balls_remaining"].to_numpy(dtype=float)
        cols = [
            needed,
            left,
            wickets,
            frame["required_rate"].to_numpy(dtype=float),
            np.log1p(needed) - np.log1p(left),
            wickets * left / 120,
        ]
    cols.append(frame["runs_last_12"].to_numpy(dtype=float))
    return np.column_stack(cols)


def fit_baseline(train: pd.DataFrame, innings_no: int) -> Pipeline:
    """Ties (label 0.5) enter as half a win and half a loss."""
    x = _baseline_matrix(train, innings_no)
    y = train[LABEL].to_numpy()
    tie = y == 0.5
    xs = np.vstack([x[~tie], x[tie], x[tie]])
    ys = np.concatenate([y[~tie], np.zeros(tie.sum()), np.ones(tie.sum())])
    ws = np.concatenate([np.ones((~tie).sum()), np.full(tie.sum() * 2, 0.5)])
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    model.fit(xs, ys, logisticregression__sample_weight=ws)
    return model


def baseline_predict(model: Pipeline, frame: pd.DataFrame, innings_no: int) -> np.ndarray:
    return np.asarray(model.predict_proba(_baseline_matrix(frame, innings_no))[:, 1])


# ---------------------------------------------------------------- the protocol

Method = Literal["none", "platt"]
IDENTITY = Platt(1.0, 0.0)


@dataclass
class TrainResult:
    model: WinProbabilityModel
    evaluation: dict[str, Any]
    # The headline model's test predictions, ball by ball (for comparisons).
    predictions: pd.DataFrame | None = None


def _tune(
    cfg: WinProbabilityConfig, train: pd.DataFrame, valid: pd.DataFrame, innings_no: int, log: Log
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    tr = train[train["innings_no"] == innings_no]
    va = valid[valid["innings_no"] == innings_no]
    features = cfg.served_features()[innings_no]
    results = []
    best: tuple[float, dict[str, Any], int] | None = None
    for choice in cfg.lightgbm.candidates():
        fitted = fit_booster(cfg, tr, innings_no, choice, valid=va)
        p = sigmoid(raw_logit(fitted, va, features))
        score = metrics.log_loss(va[LABEL].to_numpy(), p)
        results.append({**choice, "rounds": fitted.rounds, "valid_log_loss": score})
        log(f"    innings {innings_no} {choice} -> {fitted.rounds} rounds, log loss {score:.4f}")
        if best is None or score < best[0]:
            best = (score, choice, fitted.rounds)
    assert best is not None
    return best[1], best[2], results


def _fit_for(
    cfg: WinProbabilityConfig,
    data: pd.DataFrame,
    number: int,
    choice: dict[str, Any],
    rounds: int,
    features: list[str],
    *,
    before: int,
    method: Method,
) -> tuple[Fitted, Platt]:
    """Fit on seasons before ``before`` the way ``method`` prescribes.

    ``none`` trains on every one of those seasons. ``platt`` holds the last two
    back and calibrates on them.
    """
    if method == "none":
        fitted = fit_booster(
            cfg, data[data["season"] < before], number, choice, features=features, rounds=rounds
        )
        return fitted, IDENTITY
    tr = data[data["season"] < before - 2]
    ca = data[data["season"].isin([before - 2, before - 1])]
    fitted = fit_booster(cfg, tr, number, choice, features=features, rounds=rounds)
    return fitted, Platt.fit(raw_logit(fitted, ca, features), ca[LABEL].to_numpy())


def _rolling(
    cfg: WinProbabilityConfig,
    data: pd.DataFrame,
    number: int,
    choice: dict[str, Any],
    rounds: int,
    features: list[str],
    season: int,
    method: Method,
) -> tuple[np.ndarray, np.ndarray]:
    """One rolling-origin step: predict ``season`` from earlier seasons only."""
    te = evaluable(data[data["season"] == season])
    fitted, platt = _fit_for(
        cfg, data, number, choice, rounds, features, before=season, method=method
    )
    return te[LABEL].to_numpy(), sigmoid(platt(raw_logit(fitted, te, features)))


def _pretest_seasons(cfg: WinProbabilityConfig, labelled: pd.DataFrame) -> list[int]:
    return [
        int(s)
        for s in sorted(labelled["season"].unique())
        if cfg.splits.backtest_from <= s <= max(cfg.splits.validation)
    ]


def _rolling_score(
    cfg: WinProbabilityConfig,
    labelled: pd.DataFrame,
    choices: dict[int, dict[str, Any]],
    rounds: dict[int, int],
    method: Method,
    features: dict[int, list[str]],
) -> tuple[float, float]:
    ys, ps = [], []
    for number, feats in features.items():
        data = labelled[labelled["innings_no"] == number]
        for season in _pretest_seasons(cfg, labelled):
            y, p = _rolling(
                cfg, data, number, choices[number], rounds[number], feats, season, method
            )
            ys.append(y)
            ps.append(p)
    y_all, p_all = np.concatenate(ys), np.concatenate(ps)
    return metrics.log_loss(y_all, p_all), metrics.brier(y_all, p_all)


def _choose_calibration(
    cfg: WinProbabilityConfig,
    labelled: pd.DataFrame,
    choices: dict[int, dict[str, Any]],
    rounds: dict[int, int],
    log: Log,
) -> tuple[Method, list[dict[str, Any]]]:
    """Calibrate or not? Decided on pre-test seasons with the rolling origin.

    Calibrating on the latest seasons tracks drift in the scoring era but costs
    those seasons as training data, and a season-specific shift (dew, the toss)
    can overshoot. Which wins is an empirical question, so it is measured.
    """
    table: list[dict[str, Any]] = []
    methods: tuple[Method, ...] = ("none", "platt")
    for method in methods:
        loss, brier = _rolling_score(cfg, labelled, choices, rounds, method, cfg.served_features())
        table.append({"method": method, "log_loss": loss, "brier": brier})
        log(f"    {method:5} log loss {loss:.4f}, brier {brier:.4f}")
    best = min(table, key=lambda r: float(r["log_loss"]))
    return cast(Method, best["method"]), table


def by_competition(
    frame: pd.DataFrame, y: np.ndarray, p: np.ndarray, base: np.ndarray
) -> list[dict[str, Any]]:
    """Test metrics in each competition (pooled models), against the baseline."""
    if "competition_id" not in frame or frame["competition_id"].nunique() < 2:
        return []
    out = []
    competitions = frame["competition_id"].to_numpy()
    groups = frame["match_id"].to_numpy()
    for competition in sorted(set(competitions)):
        mask = competitions == competition
        out.append(
            {
                "competition": str(competition),
                "matches": int(frame.loc[mask, "match_id"].nunique()),
                "model": metrics.summarize(y[mask], p[mask]),
                "baseline": metrics.summarize(y[mask], base[mask]),
                "vs_baseline": metrics.paired_bootstrap(groups[mask], y[mask], p[mask], base[mask]),
            }
        )
    return out


def _by_phase(frame: pd.DataFrame, p: np.ndarray, base: np.ndarray) -> list[dict[str, Any]]:
    out = []
    phases = phase_of(frame["legal_balls"]).to_numpy()
    y = frame[LABEL].to_numpy()
    for number in (1, 2):
        for phase in ("powerplay", "middle", "death"):
            mask = (frame["innings_no"].to_numpy() == number) & (phases == phase)
            if not mask.any():
                continue
            out.append(
                {
                    "innings_no": number,
                    "phase": phase,
                    "rows": int(mask.sum()),
                    "model_log_loss": metrics.log_loss(y[mask], p[mask]),
                    "baseline_log_loss": metrics.log_loss(y[mask], base[mask]),
                    "model_brier": metrics.brier(y[mask], p[mask]),
                    "baseline_brier": metrics.brier(y[mask], base[mask]),
                }
            )
    return out


def train_model(
    states: pd.DataFrame, cfg: WinProbabilityConfig, *, data_version: str, log: Log = _quiet
) -> TrainResult:
    started = time.perf_counter()
    labelled = trainable(states)
    splits = cfg.splits
    train = _upto(labelled, splits.train_through)
    valid = _seasons(labelled, splits.validation)
    test = evaluable(_seasons(labelled, splits.test))
    first_test = min(splits.test)

    log("> tuning on validation seasons")
    choices: dict[int, dict[str, Any]] = {}
    rounds: dict[int, int] = {}
    grid: dict[str, list[dict[str, Any]]] = {}
    for number in (1, 2):
        choices[number], rounds[number], grid[str(number)] = _tune(cfg, train, valid, number, log)

    log("> choosing calibration (rolling origin, pre-test seasons)")
    method, calibration_table = _choose_calibration(cfg, labelled, choices, rounds, log)
    other: Method = "platt" if method == "none" else "none"
    log(f"    chose {method}")

    log("> scoring the test seasons")
    preds: dict[str, list[np.ndarray]] = {k: [] for k in ("model", "other", "iso", "base", "state")}
    frames = []
    keys = group_keys(cfg.served_features())
    importance: dict[str, float] = dict.fromkeys(keys, 0.0)
    per_innings = []
    for number in (1, 2):
        data = labelled[labelled["innings_no"] == number]
        te = test[test["innings_no"] == number]
        y = te[LABEL].to_numpy()
        features, state_features = cfg.served_features()[number], STATE_FEATURES[number]
        args = (cfg, data, number, choices[number], rounds[number])

        fitted, platt = _fit_for(*args, features, before=first_test, method=method)
        p_model = sigmoid(platt(raw_logit(fitted, te, features)))
        alt, alt_platt = _fit_for(*args, features, before=first_test, method=other)
        p_other = sigmoid(alt_platt(raw_logit(alt, te, features)))

        # Isotonic, for comparison: the model without the last two seasons, calibrated on them.
        held, _ = _fit_for(*args, features, before=first_test, method="platt")
        ca = data[data["season"].isin([first_test - 2, first_test - 1])]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(
            sigmoid(raw_logit(held, ca, features)), ca[LABEL].to_numpy()
        )
        p_iso = np.asarray(iso.predict(sigmoid(raw_logit(held, te, features))))

        state_fit, state_platt = _fit_for(*args, state_features, before=first_test, method=method)
        p_state = sigmoid(state_platt(raw_logit(state_fit, te, state_features)))
        baseline = fit_baseline(data[data["season"] < first_test], number)
        p_base = baseline_predict(baseline, te, number)

        for key, value in (
            ("model", p_model),
            ("other", p_other),
            ("iso", p_iso),
            ("base", p_base),
            ("state", p_state),
        ):
            preds[key].append(value)
        frames.append(te)
        per_innings.append(
            {
                "innings_no": number,
                "model": metrics.summarize(y, p_model),
                "baseline": metrics.summarize(y, p_base),
                "state_only": metrics.summarize(y, p_state),
            }
        )
        _, grouped = InningsModel(number, fitted.booster, platt, tuple(features)).explain(te, keys)
        for g, key in enumerate(keys):
            importance[key] += float(np.abs(grouped[:, g]).sum())

    frame = pd.concat(frames)
    y = frame[LABEL].to_numpy()
    p = {k: np.concatenate(v) for k, v in preds.items()}
    groups = frame["match_id"].to_numpy()
    total_importance = sum(importance.values()) or 1.0

    log("> feature selection: candidate context groups (rolling origin, pre-test seasons)")
    selection = _feature_selection(cfg, labelled, choices, rounds, method, log)

    log("> rolling-origin backtest")
    backtest = _backtest(labelled, cfg, choices, rounds, method, log)

    log("> fitting the served model on every season")
    model = _fit_served(labelled, cfg, choices, rounds, method, log)

    evaluation: dict[str, Any] = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "splits": {
            "train": [int(train["season"].min()), splits.train_through],
            "validation": splits.validation,
            "test": splits.test,
            "served_through": int(labelled["season"].max()),
        },
        "calibration": {"method": method, "selection": calibration_table},
        "test": {
            "matches": int(frame["match_id"].nunique()),
            "model": metrics.summarize(y, p["model"]),
            "alternatives": [
                {"key": other, **metrics.summarize(y, p["other"])},
                {"key": "isotonic", **metrics.summarize(y, p["iso"])},
            ],
            "baseline": metrics.summarize(y, p["base"]),
            "state_only": metrics.summarize(y, p["state"]),
            "vs_baseline": metrics.paired_bootstrap(groups, y, p["model"], p["base"]),
            "vs_state_only": metrics.paired_bootstrap(groups, y, p["model"], p["state"]),
            "reliability": metrics.reliability(y, p["model"]),
            "baseline_reliability": metrics.reliability(y, p["base"]),
            "by_innings": per_innings,
            "by_phase": _by_phase(frame, p["model"], p["base"]),
            "by_competition": by_competition(frame, y, p["model"], p["base"]),
        },
        "importance": {k: v / total_importance for k, v in importance.items()},
        "feature_selection": selection,
        "backtest": backtest,
        "tuning": {
            "chosen": {str(k): v for k, v in choices.items()},
            "rounds": {str(k): v for k, v in rounds.items()},
            "grid": grid,
        },
        "training_seconds": round(time.perf_counter() - started, 1),
    }
    model.manifest["headline"] = {
        "test_log_loss": evaluation["test"]["model"]["log_loss"],
        "test_brier": evaluation["test"]["model"]["brier"],
        "test_seasons": splits.test,
    }
    keys = [c for c in ("match_id", "innings_no", "seq_no", "competition_id") if c in frame]
    predictions = frame[keys].assign(y=y, p=p["model"], baseline=p["base"])
    return TrainResult(model=model, evaluation=evaluation, predictions=predictions)


def _feature_selection(
    cfg: WinProbabilityConfig,
    labelled: pd.DataFrame,
    choices: dict[int, dict[str, Any]],
    rounds: dict[int, int],
    method: Method,
    log: Log,
) -> list[dict[str, Any]]:
    """Does any candidate context group improve on the served features?

    Each group is added to the served set and scored with the rolling-origin
    protocol on the seasons *before* the test seasons (never on test).
    """
    seasons = _pretest_seasons(cfg, labelled)
    table = []
    for number in (1, 2):
        served = cfg.served_features()[number]
        variants = {"served": served} | {
            f"+{key}": served + extra
            for key, groups in CANDIDATES.items()
            if key not in cfg.served_extras.get(number, []) and (extra := groups[number])
        }
        for name, features in variants.items():
            loss, brier = _rolling_score(cfg, labelled, choices, rounds, method, {number: features})
            table.append(
                {
                    "innings_no": number,
                    "variant": name,
                    "features": features,
                    "log_loss": loss,
                    "brier": brier,
                    "seasons": [seasons[0], seasons[-1]],
                }
            )
            log(f"    innings {number} {name:14} log loss {loss:.4f}")
    return table


def _backtest(
    labelled: pd.DataFrame,
    cfg: WinProbabilityConfig,
    choices: dict[int, dict[str, Any]],
    rounds: dict[int, int],
    method: Method,
    log: Log,
) -> list[dict[str, Any]]:
    seasons = sorted(int(s) for s in labelled["season"].unique() if s >= cfg.splits.backtest_from)
    table = []
    for season in seasons:
        ys, pm, pb = [], [], []
        for number in (1, 2):
            data = labelled[labelled["innings_no"] == number]
            y, p = _rolling(
                cfg,
                data,
                number,
                choices[number],
                rounds[number],
                cfg.served_features()[number],
                season,
                method,
            )
            te = evaluable(data[data["season"] == season])
            base = fit_baseline(data[data["season"] < season], number)
            ys.append(y)
            pm.append(p)
            pb.append(baseline_predict(base, te, number))
        y, m, b = np.concatenate(ys), np.concatenate(pm), np.concatenate(pb)
        row = {
            "season": season,
            "matches": int(labelled.loc[labelled["season"] == season, "match_id"].nunique()),
            "model_log_loss": metrics.log_loss(y, m),
            "baseline_log_loss": metrics.log_loss(y, b),
            "model_brier": metrics.brier(y, m),
            "baseline_brier": metrics.brier(y, b),
            "model_ece": metrics.ece(y, m),
        }
        log(
            f"    {season}: log loss {row['model_log_loss']:.4f} "
            f"(baseline {row['baseline_log_loss']:.4f})"
        )
        table.append(row)
    return table


def _fit_served(
    labelled: pd.DataFrame,
    cfg: WinProbabilityConfig,
    choices: dict[int, dict[str, Any]],
    rounds: dict[int, int],
    method: Method,
    log: Log,
    folds: int = 5,
) -> WinProbabilityModel:
    seasons = sorted(int(s) for s in labelled["season"].unique())
    fold_of = {s: i % folds for i, s in enumerate(seasons)}
    innings: dict[int, InningsModel] = {}
    for number in (1, 2):
        data = labelled[labelled["innings_no"] == number]
        features = cfg.served_features()[number]
        platt = IDENTITY
        if method == "platt":
            # Out-of-fold predictions by season, calibrated on the most recent seasons.
            oof = np.empty(len(data))
            fold = data["season"].map(fold_of).to_numpy()
            for k in range(folds):
                held = fold == k
                fitted = fit_booster(
                    cfg, data[~held], number, choices[number], rounds=rounds[number]
                )
                oof[held] = raw_logit(fitted, data[held], features)
            recent = (data["season"] > seasons[-1] - cfg.calibration_recent_seasons).to_numpy()
            platt = Platt.fit(oof[recent], data.loc[recent, LABEL].to_numpy())
        final = fit_booster(cfg, data, number, choices[number], rounds=rounds[number])
        innings[number] = InningsModel(number, final.booster, platt, tuple(features))
        log(
            f"    innings {number}: {rounds[number]} rounds, "
            f"calibration a={platt.a:.3f} b={platt.b:.3f}"
        )

    manifest: dict[str, Any] = {
        "name": cfg.name,
        "features": {str(k): v for k, v in cfg.served_features().items()},
        "feature_config": asdict(cfg.feature_config()),
        "monotone": {str(k): MONOTONE[k] for k in (1, 2)},
        "groups": group_keys(cfg.served_features()),
        "params": {str(k): choices[k] for k in (1, 2)},
        "rounds": {str(k): rounds[k] for k in (1, 2)},
        "calibration_method": method,
        "trained_on": {
            "seasons": [seasons[0], seasons[-1]],
            "matches": int(labelled["match_id"].nunique()),
            "rows": len(labelled),
            **(
                {"competitions": sorted(labelled["competition_id"].unique().tolist())}
                if "competition_id" in labelled
                else {}
            ),
        },
        "lightgbm": package_version("lightgbm"),
    }
    manifest["base_probability"] = {str(n): m.base_probability() for n, m in innings.items()}
    return WinProbabilityModel(version=cfg.version, innings=innings, manifest=manifest)
