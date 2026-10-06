"""First-innings score projection: calibrated quantiles of the final total.

* **Target.** The runs still to come, divided by what the scoring era would
  expect from the balls left (``env_rpb * balls_remaining``). The ratio keeps
  one model valid from 2008 to 2026 even though totals rose by 30 runs, and it
  lets trees work in a range they have seen.
* **Model.** One LightGBM quantile model per level in ``LEVELS``. LightGBM
  cannot combine monotonic constraints with the quantile objective, so the
  direction of wickets is checked by a sanity test instead. Crossing quantiles
  are sorted.
* **Calibration.** Conformal, per level: on held-out predictions, level tau is
  shifted by the tau-quantile of its errors, so that about tau of totals fall
  below it. The 80% range is the 10% to 90% quantiles.

Only the first innings is projected. A chase is capped by its target, so its
"final score" is not a useful quantity (the win probability covers chases).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from criciq_ml.features import FeatureConfig

FloatArray = NDArray[np.float64]

LEVELS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
MEDIAN = LEVELS.index(0.5)
LOW80, HIGH80 = LEVELS.index(0.1), LEVELS.index(0.9)

FEATURES = [
    "legal_balls",
    "balls_remaining",
    "wickets",
    "runs_vs_par",
    "run_rate_rel",
    "runs_last_12",
    "wickets_last_12",
]

# Candidate context features, tested by adding each group to the served set.
CANDIDATES: dict[str, list[str]] = {
    "crease": ["crease_sr_idx", "crease_avg_idx", "crease_balls"],
    "depth": ["depth_avg_sum"],
    "bowling": ["bowl_left_econ_idx"],
    "venue": ["venue_idx"],
    # Pooled data: the competition's scoring level, and international cricket.
    "era": ["env_rpb"],
    "international": ["international"],
}

TARGET = "remaining_ratio"


def projection_frame(states: pd.DataFrame) -> pd.DataFrame:
    """First-innings states with the target, derived features and bookkeeping.

    ``projectable`` marks states where there is still something to project;
    ``complete`` marks innings that ran their full course (not cut short by
    rain), the only ones used to train and evaluate.
    """
    first = states[states["innings_no"] == 1].copy()
    last = first.groupby("match_id").tail(1).set_index("match_id")
    final_runs = first["match_id"].map(last["runs"])
    complete = (last["wickets"] >= 10) | (last["legal_balls"] >= last["max_balls"] - 1)
    first["final_runs"] = final_runs
    first["complete"] = first["match_id"].map(complete).astype(bool)
    first["expected_rest"] = first["env_rpb"] * first["balls_remaining"]
    first["projectable"] = (first["balls_remaining"] > 0) & (first["wickets"] < 10)
    legal = first["legal_balls"].where(first["legal_balls"] > 0)
    first["run_rate_rel"] = first["runs"] / (first["env_rpb"] * legal)
    first[TARGET] = (first["final_runs"] - first["runs"]) / first["expected_rest"].where(
        first["projectable"]
    )
    return first


def trainable(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["complete"] & frame["projectable"]]


# ---------------------------------------------------------------- the model


def _params(
    base: dict[str, Any], choice: dict[str, Any], level: float, features: list[str]
) -> dict[str, Any]:
    return {
        **{
            k: v
            for k, v in base.items()
            if k not in {"max_rounds", "early_stopping_rounds", "num_threads"}
        },
        **choice,
        "objective": "quantile",
        "alpha": level,
        "deterministic": True,
        "force_row_wise": True,
        # Results are reproducible for a given thread count (v1 used 4).
        "num_threads": int(base.get("num_threads", 4)),
        "verbosity": -1,
    }


def fit_quantiles(
    base: dict[str, Any],
    choice: dict[str, Any],
    train: pd.DataFrame,
    *,
    features: list[str],
    rounds: dict[float, int] | None = None,
    valid: pd.DataFrame | None = None,
) -> tuple[dict[float, lgb.Booster], dict[float, int]]:
    """One booster per level; with ``valid`` and no ``rounds``, rounds come from early stopping."""
    x = train[features].to_numpy(dtype=np.float64)
    data = lgb.Dataset(
        x, label=train[TARGET].to_numpy(), feature_name=features, free_raw_data=False
    )
    boosters, used = {}, {}
    for level in LEVELS:
        params = _params(base, choice, level, features)
        if rounds is None and valid is not None:
            vdata = data.create_valid(
                valid[features].to_numpy(dtype=np.float64), label=valid[TARGET].to_numpy()
            )
            booster = lgb.train(
                params,
                data,
                num_boost_round=int(base["max_rounds"]),
                valid_sets=[vdata],
                callbacks=[lgb.early_stopping(int(base["early_stopping_rounds"]), verbose=False)],
            )
            used[level] = booster.best_iteration or booster.current_iteration()
        else:
            assert rounds is not None
            booster = lgb.train(params, data, num_boost_round=rounds[level])
            used[level] = rounds[level]
        boosters[level] = booster
    return boosters, used


def raw_ratios(
    boosters: dict[float, lgb.Booster], frame: pd.DataFrame, features: list[str]
) -> FloatArray:
    x = frame[features].to_numpy(dtype=np.float64)
    return np.column_stack([np.asarray(boosters[level].predict(x)) for level in LEVELS])


def conformal_shifts(raw: FloatArray, target: FloatArray) -> FloatArray:
    """Per-level shift so that each level's share of targets below it matches the level."""
    errors = target[:, None] - np.sort(raw, axis=1)
    return np.array([np.quantile(errors[:, i], level) for i, level in enumerate(LEVELS)])


def to_totals(
    ratios: FloatArray, frame: pd.DataFrame, shifts: FloatArray | None = None
) -> FloatArray:
    """Quantiles of the final total, in runs (sorted, never below the current score)."""
    adjusted = np.sort(ratios, axis=1) + (0 if shifts is None else shifts)
    adjusted = np.sort(np.maximum(adjusted, 0.0), axis=1)
    expected = frame["expected_rest"].to_numpy(dtype=np.float64)[:, None]
    current = frame["runs"].to_numpy(dtype=np.float64)[:, None]
    return np.asarray(current + adjusted * expected, dtype=np.float64)


@dataclass
class ScoreProjectionModel:
    version: str
    boosters: dict[float, lgb.Booster]
    shifts: FloatArray
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def features(self) -> list[str]:
        return list(self.manifest.get("features", FEATURES))

    @property
    def feature_config(self) -> FeatureConfig:
        """The match-state settings the model was trained with (v1: the defaults)."""
        return FeatureConfig.of(self.manifest.get("feature_config"))

    def predict(self, frame: pd.DataFrame) -> FloatArray:
        return to_totals(raw_ratios(self.boosters, frame, self.features), frame, self.shifts)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for level, booster in self.boosters.items():
            booster.save_model(str(directory / f"q{round(level * 100):02d}.txt"))
        manifest = {
            **self.manifest,
            "version": self.version,
            "levels": list(LEVELS),
            "shifts": [float(s) for s in self.shifts],
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

    @classmethod
    def load(cls, directory: Path) -> ScoreProjectionModel:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if tuple(manifest["levels"]) != LEVELS:
            raise ValueError(f"model {directory} uses different quantile levels")
        boosters = {
            level: lgb.Booster(model_file=str(directory / f"q{round(level * 100):02d}.txt"))
            for level in LEVELS
        }
        return cls(
            version=manifest["version"],
            boosters=boosters,
            shifts=np.asarray(manifest["shifts"], dtype=np.float64),
            manifest=manifest,
        )


# ---------------------------------------------------------------- probabilities


def cdf_points(quantiles: FloatArray, current: float) -> tuple[FloatArray, FloatArray]:
    """Piecewise-linear CDF of the final total through the quantiles.

    It starts at the current score (the total cannot go down) and ends a little
    beyond the 95% quantile, extending the top of the distribution by twice the
    90-95% gap. The web app uses the same construction.
    """
    top = quantiles[-1] + 2 * (quantiles[-1] - quantiles[-2]) + 1.0
    xs = np.concatenate([[min(current, quantiles[0])], quantiles, [top]])
    ps = np.concatenate([[0.0], np.asarray(LEVELS), [1.0]])
    return np.maximum.accumulate(xs), ps


def probability_at_least(
    quantiles: FloatArray, current: FloatArray, threshold: float
) -> FloatArray:
    """P(final total >= threshold) for each row."""
    out = np.empty(len(quantiles))
    for i, (q, now) in enumerate(zip(quantiles, current, strict=True)):
        if threshold <= now:
            out[i] = 1.0
            continue
        xs, ps = cdf_points(q, float(now))
        out[i] = 1.0 - float(np.interp(threshold, xs, ps))
    return out
