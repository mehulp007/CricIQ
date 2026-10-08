"""Test win probability: the batting side wins, the match is drawn, or it loses.

The model (``criciq_core.test_win_probability``) is a multinomial logistic
regression per innings. The **baseline** is the same regression on the match
state alone: the lead (or the runs needed in the fourth innings), wickets in
hand, the overs left and the scoring era. The **model** adds context known
before the match, in groups chosen on the pre-test years: the sides' ratings
from earlier Tests, home advantage, the XIs' Test records, the batting still to
come. Each enters as itself and scaled by the share of the match left.

Why not boosted trees, as for limited-overs cricket? Every ball of a Test shares
one result, and there are only about 800 Tests: trees split on the pre-match
context (the same for a whole match) and memorise individual matches. The
protocol fits them on the same rolling origin and reports how they did
(``alternatives``), so the choice stays measured.

The protocol:

1. **Context groups**: per innings, added one at a time while they improve the
   pooled log loss of a rolling origin over the pre-test years (each year
   predicted by a fit on every earlier year). A single validation pair of years
   holds about 80 Tests, too few to choose on.
2. Score the **test** years once, from a fit on every earlier year, against the
   baseline.
3. **Backtest**: each year from ``backtest_from``, fit on every earlier year.
4. Fit the **served model** on every year.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from joblib import Parallel, delayed
from numpy.typing import NDArray
from pydantic import BaseModel, Field
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from criciq_core.test_win_probability import GROUPS, OUTCOMES, InningsTerms, design
from criciq_ml import formats
from criciq_ml.test_match.states import DRAWN, LABEL, LOST, WON, TestFeatureConfig, final_rows

FloatArray = NDArray[np.float64]
Log = Callable[[str], None]
EPS = 1e-6
INNINGS = (1, 2, 3, 4)


def _quiet(_: str) -> None:
    return None


# ---------------------------------------------------------------- configuration


class Splits(BaseModel):
    validation: list[int]
    test: list[int]
    backtest_from: int


class TestWinProbabilityConfig(BaseModel):
    __test__ = False  # not a pytest test class

    name: str
    version: str
    scope: str = "TEST"
    splits: Splits
    features: dict[str, float | int]
    # Context groups served per innings; unset: chosen by forward selection.
    served_extras: dict[int, list[str]] | None = None
    # Inverse L2 strength of the regressions (on standardised features).
    c: float = 1.0
    # Fits use every n-th state of an innings (neighbouring balls say almost the same).
    train_every: int = Field(default=1, ge=1)
    # Boosted trees fitted on the same rolling origin, for comparison (not served).
    alternatives: dict[str, Any] = Field(default_factory=dict)
    n_jobs: int = 1

    def feature_config(self) -> TestFeatureConfig:
        return TestFeatureConfig(**self.features)  # type: ignore[arg-type]


def load_test_wp_config(path: Path | None = None) -> TestWinProbabilityConfig:
    source = path or formats.config_path("win_probability")
    with source.open(encoding="utf-8") as fh:
        return TestWinProbabilityConfig.model_validate(yaml.safe_load(fh))


# ---------------------------------------------------------------- metrics


def onehot(y: NDArray[np.int64]) -> FloatArray:
    out = np.zeros((len(y), 3))
    out[np.arange(len(y)), y] = 1.0
    return out


def log_loss(y: NDArray[np.int64], p: FloatArray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], EPS, 1.0)).mean())


def brier(y: NDArray[np.int64], p: FloatArray) -> float:
    return float(((p - onehot(y)) ** 2).sum(axis=1).mean())


def reliability(y: NDArray[np.int64], p: FloatArray, bins: int = 10) -> dict[str, Any]:
    """Predicted against observed frequency of each outcome, in probability bins."""
    edges = np.linspace(0, 1, bins + 1)
    out: dict[str, Any] = {}
    for k, name in enumerate(OUTCOMES):
        pk, yk = p[:, k], (y == k).astype(float)
        index = np.clip(np.digitize(pk, edges[1:-1]), 0, bins - 1)
        rows = []
        for b in range(bins):
            mask = index == b
            if mask.any():
                rows.append(
                    {
                        "lower": float(edges[b]),
                        "upper": float(edges[b + 1]),
                        "predicted": float(pk[mask].mean()),
                        "observed": float(yk[mask].mean()),
                        "count": int(mask.sum()),
                    }
                )
        gap = sum(r["count"] * abs(r["predicted"] - r["observed"]) for r in rows) / len(y)
        out[name] = {"ece": float(gap), "bins": rows}
    return out


def summarize(y: NDArray[np.int64], p: FloatArray) -> dict[str, Any]:
    return {
        "rows": len(y),
        "log_loss": log_loss(y, p),
        "brier": brier(y, p),
        "ece": {name: v["ece"] for name, v in reliability(y, p).items()},
    }


def paired_bootstrap(
    matches: NDArray[np.int64],
    y: NDArray[np.int64],
    p_model: FloatArray,
    p_base: FloatArray,
    *,
    resamples: int = 1000,
    seed: int = 7,
) -> dict[str, float]:
    """Log-loss improvement over the baseline with a 95% interval, resampling whole
    matches (a Test's balls share one result). Positive = the model is better."""
    rows = np.arange(len(y))
    loss_m = -np.log(np.clip(p_model[rows, y], EPS, 1.0))
    loss_b = -np.log(np.clip(p_base[rows, y], EPS, 1.0))
    ids, inverse = np.unique(matches, return_inverse=True)
    diff = np.bincount(inverse, weights=loss_b - loss_m)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(resamples, len(ids)))
    stats = diff[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {
        "improvement": float(diff.sum() / counts.sum()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "matches": len(ids),
    }


# ---------------------------------------------------------------- the model


@dataclass
class TestWinProbabilityModel:
    """One multinomial regression per innings; probabilities are the batting side's."""

    __test__ = False  # not a pytest test class

    terms: dict[int, InningsTerms]
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def feature_config(self) -> TestFeatureConfig:
        return TestFeatureConfig.of(self.manifest.get("feature_config"))

    def predict(self, states: pd.DataFrame) -> FloatArray:
        """(lost, drawn, won) for the batting side of every state."""
        return _predict(self.terms, states)

    def serving_info(self) -> dict[str, Any]:
        """What the API needs to run the model (the chase what-if)."""
        return {
            "terms": {str(n): t.to_json() for n, t in sorted(self.terms.items())},
            "feature_config": self.manifest.get("feature_config", {}),
        }

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "terms.json").write_text(
            json.dumps({str(n): t.to_json() for n, t in sorted(self.terms.items())}, indent=1)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @classmethod
    def load(cls, directory: Path) -> TestWinProbabilityModel:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        raw = json.loads((directory / "terms.json").read_text(encoding="utf-8"))
        return cls({int(n): InningsTerms.from_json(t) for n, t in raw.items()}, manifest)


def _predict(terms: dict[int, InningsTerms], states: pd.DataFrame) -> FloatArray:
    out = np.zeros((len(states), 3))
    numbers = states["innings_no"].to_numpy()
    for number, fitted in terms.items():
        mask = numbers == number
        if mask.any():
            out[mask] = fitted.probabilities(states[mask])
    return out


# ---------------------------------------------------------------- fitting


def labelled(states: pd.DataFrame) -> pd.DataFrame:
    return states[states[LABEL].notna()]


def evaluable(states: pd.DataFrame) -> pd.DataFrame:
    """Rows a model is judged on: not a match's last ball, where the result is known
    (served from the result itself, not the model)."""
    return states[~final_rows(states)]


def _thin(frame: pd.DataFrame, every: int) -> pd.DataFrame:
    """Every n-th state of each innings (and every innings' start)."""
    if every <= 1:
        return frame
    return frame[frame["seq_no"] % every == 0]


def fit_innings(
    train: pd.DataFrame, number: int, groups: list[str], c: float, every: int = 1
) -> InningsTerms:
    """One innings' regression on ``train`` (that innings' states)."""
    rows = _thin(train, every)
    x, names = design(rows, number, groups)
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(C=c, max_iter=3000)
    model.fit(scaler.transform(x), rows[LABEL].to_numpy().astype(int))
    coef = np.zeros((3, x.shape[1]))
    intercept = np.full(3, -30.0)  # an outcome never seen in training stays impossible
    classes = model.classes_.astype(int)
    if len(classes) == 2:  # a binary fit has one row of coefficients
        coef[classes[1]] = model.coef_[0]
        intercept[classes] = [0.0, float(model.intercept_[0])]
    else:
        coef[classes] = model.coef_
        intercept[classes] = model.intercept_
    scale = np.where(scaler.scale_ > 0, scaler.scale_, 1.0)
    return InningsTerms(number, tuple(groups), tuple(names), scaler.mean_, scale, coef, intercept)


def _labels(frame: pd.DataFrame) -> NDArray[np.int64]:
    return np.asarray(frame[LABEL].to_numpy(), dtype=np.int64)


def _year_fold(
    data: pd.DataFrame, season: int, number: int, groups: list[str], c: float, every: int
) -> tuple[FloatArray, NDArray[np.int64], NDArray[np.int64]]:
    """One rolling-origin step for one innings: predict ``season`` from earlier years."""
    rows = data[data["innings_no"] == number]
    target = evaluable(data[data["season"] == season])
    target = target[target["innings_no"] == number]
    terms = fit_innings(rows[rows["season"] < season], number, groups, c, every)
    return terms.probabilities(target), _labels(target), target["match_id"].to_numpy()


def _rolling(
    cfg: TestWinProbabilityConfig,
    data: pd.DataFrame,
    seasons: list[int],
    number: int,
    groups: list[str],
) -> tuple[FloatArray, NDArray[np.int64], NDArray[np.int64]]:
    folds = Parallel(n_jobs=cfg.n_jobs)(
        delayed(_year_fold)(data, s, number, groups, cfg.c, cfg.train_every) for s in seasons
    )
    return (
        np.vstack([f[0] for f in folds]),
        np.concatenate([f[1] for f in folds]),
        np.concatenate([f[2] for f in folds]),
    )


def _select_groups(
    cfg: TestWinProbabilityConfig, data: pd.DataFrame, seasons: list[int], number: int, log: Log
) -> tuple[list[str], list[dict[str, Any]]]:
    """Forward selection of context groups on the pre-test rolling origin."""
    chosen: list[str] = []
    p, y, _ = _rolling(cfg, data, seasons, number, [])
    best = log_loss(y, p)
    history = [{"groups": [], "log_loss": best}]
    log(f"    innings {number}: match state only -> {best:.4f}")
    while True:
        trials = []
        for group in (g for g in GROUPS if g not in chosen):
            p, y, _ = _rolling(cfg, data, seasons, number, [*chosen, group])
            score = log_loss(y, p)
            trials.append((score, group))
            history.append({"groups": [*chosen, group], "log_loss": score})
            log(f"    innings {number}: + {group} -> {score:.4f}")
        if not trials:
            break
        score, group = min(trials)
        if score >= best:
            break
        best = score
        chosen.append(group)
    return chosen, history


def _trees(
    cfg: TestWinProbabilityConfig,
    data: pd.DataFrame,
    seasons: list[int],
    groups: dict[int, list[str]],
    log: Log,
) -> dict[str, Any]:
    """Boosted trees on the same features and rolling origin (reported, not served)."""
    import lightgbm as lgb

    settings = dict(cfg.alternatives)
    rounds = int(settings.pop("rounds", 300))
    params = {
        "objective": "multiclass",
        "num_class": 3,
        "verbosity": -1,
        "deterministic": True,
        "force_row_wise": True,
        **settings,
    }
    ys, ps = [], []
    for number in INNINGS:
        rows = data[data["innings_no"] == number]
        for season in seasons:
            train = _thin(rows[rows["season"] < season], cfg.train_every)
            target = evaluable(rows[rows["season"] == season])
            x, _ = design(train, number, groups[number])
            booster = lgb.train(params, lgb.Dataset(x, _labels(train)), rounds)
            ps.append(booster.predict(design(target, number, groups[number])[0]))
            ys.append(_labels(target))
    y, p = np.concatenate(ys), np.vstack(ps)
    found = {"model": "boosted trees", "settings": cfg.alternatives, "log_loss": log_loss(y, p)}
    log(f"    boosted trees on the same rolling origin -> {found['log_loss']:.4f}")
    return found


def _by_innings(frame: pd.DataFrame, p: FloatArray, base: FloatArray) -> list[dict[str, Any]]:
    y = _labels(frame)
    numbers = frame["innings_no"].to_numpy()
    out = []
    for number in INNINGS:
        mask = numbers == number
        if mask.any():
            out.append(
                {
                    "innings_no": number,
                    "rows": int(mask.sum()),
                    "model": summarize(y[mask], p[mask]),
                    "baseline": summarize(y[mask], base[mask]),
                }
            )
    return out


def _by_day(frame: pd.DataFrame, p: FloatArray, base: FloatArray) -> list[dict[str, Any]]:
    """Log loss by the (estimated) day of the match: overs bowled / 90."""
    y = _labels(frame)
    day = np.minimum(frame["match_overs"].to_numpy() // 90, 4).astype(int) + 1
    out = []
    for d in range(1, 6):
        mask = day == d
        if mask.any():
            out.append(
                {
                    "day": d,
                    "rows": int(mask.sum()),
                    "model_log_loss": log_loss(y[mask], p[mask]),
                    "baseline_log_loss": log_loss(y[mask], base[mask]),
                }
            )
    return out


@dataclass
class TrainResult:
    model: TestWinProbabilityModel
    evaluation: dict[str, Any]
    predictions: pd.DataFrame


def _fit_all(
    cfg: TestWinProbabilityConfig, rows: pd.DataFrame, groups: dict[int, list[str]]
) -> dict[int, InningsTerms]:
    return {
        n: fit_innings(rows[rows["innings_no"] == n], n, groups[n], cfg.c, cfg.train_every)
        for n in INNINGS
    }


def train_test_wp(
    states: pd.DataFrame,
    cfg: TestWinProbabilityConfig,
    *,
    data_version: str,
    log: Log = _quiet,
) -> TrainResult:
    started = time.perf_counter()
    data = labelled(states)
    splits = cfg.splits
    first_test = min(splits.test)
    pretest = [
        int(s)
        for s in sorted(data["season"].unique())
        if splits.backtest_from <= s <= max(splits.validation)
    ]

    groups: dict[int, list[str]] = {}
    selection: dict[str, Any] = {}
    if cfg.served_extras is None:
        log("> choosing context groups (forward selection, pre-test rolling origin)")
        for number in INNINGS:
            groups[number], selection[str(number)] = _select_groups(cfg, data, pretest, number, log)
    else:
        groups = {n: list(cfg.served_extras.get(n, [])) for n in INNINGS}
    log(f"    served groups: {groups}")

    alternatives = []
    if cfg.alternatives:
        log("> boosted trees for comparison")
        p_alt: list[FloatArray] = []
        y_alt: list[NDArray[np.int64]] = []
        for number in INNINGS:
            p, y, _ = _rolling(cfg, data, pretest, number, groups[number])
            p_alt.append(p)
            y_alt.append(y)
        mine = log_loss(np.concatenate(y_alt), np.vstack(p_alt))
        alternatives = [
            {"model": "multinomial regression (served)", "log_loss": mine},
            _trees(cfg, data, pretest, groups, log),
        ]

    log("> scoring the test years")
    test = evaluable(data[data["season"].isin(splits.test)])
    before = data[data["season"] < first_test]
    fitted = _fit_all(cfg, before, groups)
    baseline = _fit_all(cfg, before, {n: [] for n in INNINGS})
    p_model = _predict(fitted, test)
    p_base = _predict(baseline, test)
    y = _labels(test)
    matches = test["match_id"].to_numpy()
    test_eval: dict[str, Any] = {
        "matches": int(test["match_id"].nunique()),
        "model": summarize(y, p_model),
        "baseline": summarize(y, p_base),
        "vs_baseline": paired_bootstrap(matches, y, p_model, p_base),
        "by_innings": _by_innings(test, p_model, p_base),
        "by_day": _by_day(test, p_model, p_base),
        "calibration": reliability(y, p_model),
        "baseline_calibration": reliability(y, p_base),
        "outcomes": {
            name: int((test.drop_duplicates("match_id")[LABEL] == k).sum())
            for k, name in enumerate(OUTCOMES)
        },
    }
    log(
        f"    test log loss {test_eval['model']['log_loss']:.4f} "
        f"(baseline {test_eval['baseline']['log_loss']:.4f}), "
        f"brier {test_eval['model']['brier']:.4f} ({test_eval['baseline']['brier']:.4f})"
    )

    log("> backtest (each year fitted on every earlier year)")
    years = [int(s) for s in sorted(data["season"].unique()) if s >= splits.backtest_from]
    backtest = []
    per_year: dict[int, list[tuple[FloatArray, FloatArray, NDArray[np.int64]]]] = {}
    for number in INNINGS:
        folds = Parallel(n_jobs=cfg.n_jobs)(
            delayed(_backtest_fold)(cfg, data, s, number, groups[number]) for s in years
        )
        for season, fold in zip(years, folds, strict=True):
            per_year.setdefault(season, []).append(fold)
    for season in years:
        pm = np.vstack([f[0] for f in per_year[season]])
        pb = np.vstack([f[1] for f in per_year[season]])
        yy = np.concatenate([f[2] for f in per_year[season]])
        backtest.append(
            {
                "season": season,
                "matches": int(data.loc[data["season"] == season, "match_id"].nunique()),
                "model_log_loss": log_loss(yy, pm),
                "baseline_log_loss": log_loss(yy, pb),
                "model_brier": brier(yy, pm),
                "baseline_brier": brier(yy, pb),
            }
        )
        log(
            f"    {season}: {backtest[-1]['model_log_loss']:.4f} "
            f"vs {backtest[-1]['baseline_log_loss']:.4f}"
        )

    log("> fitting the served model on every year")
    served = _fit_all(cfg, data, groups)
    seasons = sorted(int(s) for s in data["season"].unique())
    trained_on = {
        "competitions": sorted(str(c) for c in data["competition_id"].unique()),
        "seasons": [seasons[0], seasons[-1]],
        "matches": int(data["match_id"].nunique()),
    }
    manifest = {
        "name": cfg.name,
        "version": cfg.version,
        "kind": "test_win_probability",
        "data_version": data_version,
        "feature_config": cfg.features,
        "groups": {str(n): groups[n] for n in INNINGS},
        "c": cfg.c,
        "trained_on": trained_on,
        "sklearn_version": package_version("scikit-learn"),
    }
    evaluation = {
        "name": cfg.name,
        "version": cfg.version,
        "data_version": data_version,
        "splits": splits.model_dump(),
        "trained_on": trained_on,
        "groups": {str(n): groups[n] for n in INNINGS},
        "features": {str(n): list(served[n].names) for n in INNINGS},
        "selection": selection,
        "selection_years": pretest,
        "alternatives": alternatives,
        "test": test_eval,
        "backtest": backtest,
        "train_seconds": round(time.perf_counter() - started, 1),
    }
    predictions = test[["match_id", "innings_no", "seq_no", "season"]].assign(
        p_lost=p_model[:, LOST], p_drawn=p_model[:, DRAWN], p_won=p_model[:, WON], label=y
    )
    return TrainResult(TestWinProbabilityModel(served, manifest), evaluation, predictions)


def _backtest_fold(
    cfg: TestWinProbabilityConfig, data: pd.DataFrame, season: int, number: int, groups: list[str]
) -> tuple[FloatArray, FloatArray, NDArray[np.int64]]:
    rows = data[data["innings_no"] == number]
    prior = rows[rows["season"] < season]
    target = evaluable(data[data["season"] == season])
    target = target[target["innings_no"] == number]
    model = fit_innings(prior, number, groups, cfg.c, cfg.train_every)
    base = fit_innings(prior, number, [], cfg.c, cfg.train_every)
    return model.probabilities(target), base.probabilities(target), _labels(target)


def gate(evaluation: dict[str, Any]) -> list[str]:
    """Reasons a version must not be promoted (empty = promote): it must beat the
    match-state baseline on the test years."""
    test = evaluation["test"]
    problems = []
    for metric in ("log_loss", "brier"):
        if test["model"][metric] >= test["baseline"][metric]:
            problems.append(f"does not beat the baseline on test {metric}")
    return problems
