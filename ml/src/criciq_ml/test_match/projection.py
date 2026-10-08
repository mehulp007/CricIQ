"""Test innings projection: calibrated quantiles of where the current innings ends.

A Test innings ends when the side is bowled out, declares, reaches a
fourth-innings target, or runs out of time, so its total depends on the match
around it: the lead, the time left and who is still to bat. One LightGBM
quantile model per level in ``LEVELS`` predicts the runs still to come in any of
the four innings (the innings number is a feature); the projection is the score
so far plus that. Conformal shifts per level, measured on held-out years, make
about tau of totals fall below level tau. Crossing quantiles are sorted.

The baseline is "par": the runs still to come at each quantile, by innings and
wickets down, measured on the training years.
"""

from __future__ import annotations

import itertools
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from criciq_ml import formats
from criciq_ml.test_match.states import TestFeatureConfig

FloatArray = NDArray[np.float64]
Log = Callable[[str], None]

LEVELS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
MEDIAN = LEVELS.index(0.5)
LOW80, HIGH80 = LEVELS.index(0.1), LEVELS.index(0.9)

FEATURES = [
    "innings_no",
    "runs",
    "wickets_in_hand",
    "legal_balls",
    "lead",
    "overs_left",
    "runs_needed",
    "follow_on",
    "innings_rpo",
    "runs_last_10",
    "wickets_last_10",
    "env_rpw",
    "env_rpo",
    "bat_left",
    "bowl_xi_opp",
]
TARGET = "remaining"


def _quiet(_: str) -> None:
    return None


def projection_frame(states: pd.DataFrame) -> pd.DataFrame:
    """Every state with its innings' final total and the runs still to come.

    ``projectable`` marks states with something left to project (not the last
    ball of an innings, nor a side all out).
    """
    frame = states.copy()
    last = frame.groupby(["match_id", "innings_no"])["runs"].transform("last")
    last_seq = frame.groupby(["match_id", "innings_no"])["seq_no"].transform("max")
    frame["final_runs"] = last
    frame[TARGET] = (last - frame["runs"]).astype(float)
    frame["projectable"] = (frame["seq_no"] < last_seq) & (frame["wickets_in_hand"] > 0)
    return frame


# ---------------------------------------------------------------- configuration


class Splits(BaseModel):
    tune_train_through: int
    tune_valid: list[int]
    calibrate: list[int]
    test: list[int]
    backtest_from: int


class LightGBMConfig(BaseModel):
    base: dict[str, Any]
    grid: dict[str, list[Any]]

    def candidates(self) -> list[dict[str, Any]]:
        keys = list(self.grid)
        return [dict(zip(keys, v, strict=True)) for v in itertools.product(*self.grid.values())]


class TestProjectionConfig(BaseModel):
    __test__ = False  # not a pytest test class

    name: str
    version: str
    scope: str = "TEST"
    splits: Splits
    train_every: int = Field(default=1, ge=1)
    lightgbm: LightGBMConfig
    gate: dict[str, list[float]]


def load_test_projection_config(path: Path | None = None) -> TestProjectionConfig:
    source = path or formats.config_path("score_projection")
    with source.open(encoding="utf-8") as fh:
        return TestProjectionConfig.model_validate(yaml.safe_load(fh))


# ---------------------------------------------------------------- metrics


def pinball(quantiles: FloatArray, y: FloatArray) -> float:
    """Mean pinball loss over the levels, in runs."""
    losses = []
    for k, tau in enumerate(LEVELS):
        diff = y - quantiles[:, k]
        losses.append(np.mean(np.maximum(tau * diff, (tau - 1) * diff)))
    return float(np.mean(losses))


def summarize(quantiles: FloatArray, y: FloatArray) -> dict[str, Any]:
    median = quantiles[:, MEDIAN]
    inside = (y >= quantiles[:, LOW80]) & (y <= quantiles[:, HIGH80])
    return {
        "rows": len(y),
        "pinball": pinball(quantiles, y),
        "mae": float(np.mean(np.abs(y - median))),
        "median_abs_error": float(np.median(np.abs(y - median))),
        "coverage80": float(inside.mean()),
        "width80": float(np.mean(quantiles[:, HIGH80] - quantiles[:, LOW80])),
        "below": [float(np.mean(y <= quantiles[:, k])) for k in range(len(LEVELS))],
    }


# ---------------------------------------------------------------- baseline


class ParBaseline:
    """Quantiles of the runs still to come by innings and wickets down."""

    def __init__(self, train: pd.DataFrame) -> None:
        keys = ["innings_no", "wickets_in_hand"]
        self.table = train.groupby(keys)[TARGET].quantile(list(LEVELS)).unstack()
        self.overall = train[TARGET].quantile(list(LEVELS)).to_numpy()

    def predict(self, frame: pd.DataFrame) -> FloatArray:
        index = pd.MultiIndex.from_frame(frame[["innings_no", "wickets_in_hand"]])
        found = self.table.reindex(index).to_numpy(dtype=float, copy=True)
        found[np.isnan(found).any(axis=1)] = self.overall
        return np.asarray(frame["runs"].to_numpy()[:, None] + found, dtype=np.float64)


# ---------------------------------------------------------------- the model


def _sorted(quantiles: FloatArray) -> FloatArray:
    return np.sort(quantiles, axis=1)


@dataclass
class TestProjectionModel:
    __test__ = False  # not a pytest test class

    boosters: list[lgb.Booster]
    shifts: FloatArray
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def feature_config(self) -> TestFeatureConfig:
        return TestFeatureConfig.of(self.manifest.get("feature_config"))

    def predict(self, frame: pd.DataFrame) -> FloatArray:
        """Quantiles of the innings' final total, never below the runs already scored."""
        raw = raw_remaining(self.boosters, frame)
        return to_totals(raw, frame, self.shifts)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for tau, booster in zip(LEVELS, self.boosters, strict=True):
            booster.save_model(str(directory / f"q{round(tau * 100):02d}.txt"))
        manifest = {**self.manifest, "shifts": [round(float(s), 4) for s in self.shifts]}
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

    @classmethod
    def load(cls, directory: Path) -> TestProjectionModel:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        boosters = [
            lgb.Booster(model_file=str(directory / f"q{round(tau * 100):02d}.txt"))
            for tau in LEVELS
        ]
        return cls(boosters, np.asarray(manifest["shifts"], dtype=float), manifest)


def raw_remaining(boosters: list[lgb.Booster], frame: pd.DataFrame) -> FloatArray:
    x = frame[FEATURES].to_numpy(dtype=np.float64)
    return np.column_stack([b.predict(x) for b in boosters])


def to_totals(raw: FloatArray, frame: pd.DataFrame, shifts: FloatArray) -> FloatArray:
    """Totals from the runs still to come: never below the score, and in the fourth innings
    never past the target (the chase ends when it is reached)."""
    remaining = np.maximum(_sorted(raw + shifts), 0.0)
    chase = frame["innings_no"].to_numpy() == 4
    cap = np.where(chase, frame["runs_needed"].to_numpy(dtype=float), np.inf)
    remaining = np.minimum(remaining, np.maximum(cap, 0.0)[:, None])
    return np.asarray(frame["runs"].to_numpy()[:, None] + remaining, dtype=np.float64)


def conformal_shifts(raw: FloatArray, remaining: FloatArray) -> FloatArray:
    """Per level, the tau-quantile of the errors: added so that about tau fall below."""
    errors = remaining[:, None] - _sorted(raw)
    return np.array([np.quantile(errors[:, k], tau) for k, tau in enumerate(LEVELS)])


def _fit(
    cfg: TestProjectionConfig,
    train: pd.DataFrame,
    choice: dict[str, Any],
    *,
    valid: pd.DataFrame | None = None,
    rounds: list[int] | None = None,
) -> tuple[list[lgb.Booster], list[int]]:
    rows = train if cfg.train_every <= 1 else train[train["seq_no"] % cfg.train_every == 0]
    base = {
        k: v
        for k, v in cfg.lightgbm.base.items()
        if k not in {"max_rounds", "early_stopping_rounds", "num_threads"}
    }
    boosters, used = [], []
    for k, tau in enumerate(LEVELS):
        params = {
            **base,
            **choice,
            "objective": "quantile",
            "alpha": tau,
            "deterministic": True,
            "force_row_wise": True,
            "num_threads": int(cfg.lightgbm.base.get("num_threads", 4)),
            "verbosity": -1,
        }
        data = lgb.Dataset(
            rows[FEATURES].to_numpy(dtype=np.float64),
            label=rows[TARGET].to_numpy(dtype=float),
            feature_name=FEATURES,
            free_raw_data=False,
        )
        if valid is not None and rounds is None:
            vdata = data.create_valid(
                valid[FEATURES].to_numpy(dtype=np.float64), label=valid[TARGET].to_numpy()
            )
            booster = lgb.train(
                params,
                data,
                num_boost_round=int(cfg.lightgbm.base["max_rounds"]),
                valid_sets=[vdata],
                callbacks=[
                    lgb.early_stopping(
                        int(cfg.lightgbm.base["early_stopping_rounds"]), verbose=False
                    )
                ],
            )
            # Predictions use the best iteration (LightGBM's default after early stopping).
            boosters.append(booster)
            used.append(booster.best_iteration or booster.current_iteration())
            continue
        booster = lgb.train(params, data, num_boost_round=rounds[k] if rounds else 300)
        boosters.append(booster)
        used.append(booster.current_iteration())
    return boosters, used


def _fit_and_calibrate(
    cfg: TestProjectionConfig,
    data: pd.DataFrame,
    choice: dict[str, Any],
    rounds: list[int],
    *,
    before: int,
) -> tuple[list[lgb.Booster], FloatArray]:
    """Fit on years before ``before - 2``, calibrate on the two years after."""
    train = data[data["season"] < before - 2]
    held = data[data["season"].isin([before - 2, before - 1])]
    boosters, _ = _fit(cfg, train, choice, rounds=rounds)
    shifts = conformal_shifts(raw_remaining(boosters, held), held[TARGET].to_numpy())
    return boosters, shifts


@dataclass
class TrainResult:
    model: TestProjectionModel
    evaluation: dict[str, Any]


def _by_innings(frame: pd.DataFrame, q: FloatArray, par: FloatArray) -> list[dict[str, Any]]:
    y = frame["final_runs"].to_numpy(dtype=float)
    numbers = frame["innings_no"].to_numpy()
    out = []
    for number in (1, 2, 3, 4):
        mask = numbers == number
        if mask.any():
            out.append(
                {
                    "innings_no": number,
                    "model": summarize(q[mask], y[mask]),
                    "par_baseline": summarize(par[mask], y[mask]),
                }
            )
    return out


def train_test_projection(
    states: pd.DataFrame,
    cfg: TestProjectionConfig,
    feature_config: dict[str, Any],
    *,
    data_version: str,
    log: Log = _quiet,
) -> TrainResult:
    started = time.perf_counter()
    frame = projection_frame(states)
    data = frame[frame["projectable"]]
    splits = cfg.splits
    tune_train = data[data["season"] <= splits.tune_train_through]
    tune_valid = data[data["season"].isin(splits.tune_valid)]

    log("> tuning on the validation years")
    grid = []
    best: tuple[float, dict[str, Any], list[int]] | None = None
    for choice in cfg.lightgbm.candidates():
        boosters, rounds = _fit(cfg, tune_train, choice, valid=tune_valid)
        q = to_totals(raw_remaining(boosters, tune_valid), tune_valid, np.zeros(len(LEVELS)))
        score = pinball(q, tune_valid["final_runs"].to_numpy(dtype=float))
        grid.append({**choice, "rounds": rounds, "valid_pinball": score})
        log(f"    {choice} -> {rounds}, pinball {score:.3f}")
        if best is None or score < best[0]:
            best = (score, choice, rounds)
    assert best is not None
    _, choice, rounds = best

    log("> scoring the test years")
    first_test = min(splits.test)
    test = data[data["season"].isin(splits.test)]
    boosters, shifts = _fit_and_calibrate(cfg, data, choice, rounds, before=first_test)
    q_model = to_totals(raw_remaining(boosters, test), test, shifts)
    par = ParBaseline(data[data["season"] < first_test]).predict(test)
    y = test["final_runs"].to_numpy(dtype=float)
    test_eval: dict[str, Any] = {
        "innings": int(test.groupby(["match_id", "innings_no"]).ngroups),
        "model": summarize(q_model, y),
        "par_baseline": summarize(par, y),
        "by_innings": _by_innings(test, q_model, par),
        "shifts": [round(float(s), 3) for s in shifts],
    }
    log(
        f"    test pinball {test_eval['model']['pinball']:.3f} "
        f"(par {test_eval['par_baseline']['pinball']:.3f}), "
        f"80% coverage {test_eval['model']['coverage80']:.1%}"
    )

    log("> backtest (each year: fit < y-2, calibrate y-2 and y-1)")
    backtest = []
    for season in range(splits.backtest_from, int(data["season"].max()) + 1):
        target = data[data["season"] == season]
        if target.empty:
            continue
        b, s = _fit_and_calibrate(cfg, data, choice, rounds, before=season)
        q = to_totals(raw_remaining(b, target), target, s)
        p = ParBaseline(data[data["season"] < season]).predict(target)
        yy = target["final_runs"].to_numpy(dtype=float)
        m, pb = summarize(q, yy), summarize(p, yy)
        backtest.append(
            {
                "season": season,
                "model_pinball": m["pinball"],
                "par_pinball": pb["pinball"],
                "model_mae": m["mae"],
                "par_mae": pb["mae"],
                "coverage80": m["coverage80"],
            }
        )
        log(f"    {season}: pinball {m['pinball']:.2f} vs {pb['pinball']:.2f}")

    log("> fitting the served model on every year")
    last = int(data["season"].max())
    boosters, shifts = _fit_and_calibrate(cfg, data, choice, rounds, before=last + 1)
    # The served trees are refit on every year; the shifts are the latest held-out ones.
    served, _ = _fit(cfg, data, choice, rounds=rounds)
    seasons = sorted(int(s) for s in data["season"].unique())
    trained_on = {
        "competitions": sorted(str(c) for c in data["competition_id"].unique()),
        "seasons": [seasons[0], seasons[-1]],
        "matches": int(data["match_id"].nunique()),
    }
    manifest = {
        "name": cfg.name,
        "version": cfg.version,
        "kind": "test_projection",
        "data_version": data_version,
        "feature_config": feature_config,
        "features": FEATURES,
        "levels": list(LEVELS),
        "choice": choice,
        "rounds": rounds,
        "trained_on": trained_on,
        "lightgbm_version": package_version("lightgbm"),
    }
    model = TestProjectionModel(served, shifts, manifest)
    evaluation = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "splits": splits.model_dump(),
        "trained_on": trained_on,
        "features": FEATURES,
        "levels": list(LEVELS),
        "grid": grid,
        "test": test_eval,
        "backtest": backtest,
        "train_seconds": round(time.perf_counter() - started, 1),
    }
    return TrainResult(model, evaluation)


def gate(evaluation: dict[str, Any], band: list[float]) -> list[str]:
    test = evaluation["test"]
    problems = []
    low, high = band
    if not low <= test["model"]["coverage80"] <= high:
        problems.append(
            f"80% range covers {test['model']['coverage80']:.1%} of test totals "
            f"(must be {low:.0%}-{high:.0%})"
        )
    for metric in ("mae", "pinball"):
        if test["model"][metric] >= test["par_baseline"][metric]:
            problems.append(f"does not beat the par baseline on test {metric}")
    return problems
