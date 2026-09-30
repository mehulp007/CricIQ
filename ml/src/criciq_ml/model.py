"""The served win probability model: two boosted-tree models plus calibration.

* ``innings1`` estimates the chance that the side batting first wins, and
  ``innings2`` the chance that the chasing side wins.
* Calibration is Platt scaling on the log-odds (``a * logit + b``). Because it
  is linear in log-odds, each feature's TreeSHAP contribution can be scaled by
  ``a`` and still add up exactly to the calibrated prediction.
* Explanations are grouped into fan-level concepts (``features.GROUPS``) and
  converted from log-odds to percentage points of win probability.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import minimize

from criciq_ml.features import FEATURES, GROUP_KEYS, GROUPS

FloatArray = NDArray[np.float64]


def logit(p: FloatArray) -> FloatArray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.asarray(np.log(p / (1 - p)), dtype=np.float64)


def sigmoid(x: FloatArray) -> FloatArray:
    return np.asarray(1.0 / (1.0 + np.exp(-x)), dtype=np.float64)


@dataclass(frozen=True)
class Platt:
    """Calibrated log-odds = a * raw log-odds + b."""

    a: float = 1.0
    b: float = 0.0

    @classmethod
    def fit(cls, raw: FloatArray, y: FloatArray) -> Platt:
        def loss(params: FloatArray) -> float:
            p = np.clip(sigmoid(params[0] * raw + params[1]), 1e-9, 1 - 1e-9)
            return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

        # The slope stays positive, so calibration can never invert the model's ranking.
        bounds = [(1e-3, None), (None, None)]
        result = minimize(loss, x0=np.array([1.0, 0.0]), method="L-BFGS-B", bounds=bounds)
        a, b = (float(v) for v in result.x)
        return cls(a=a, b=b)

    def __call__(self, raw: FloatArray) -> FloatArray:
        return np.asarray(self.a * raw + self.b, dtype=np.float64)


@dataclass
class InningsModel:
    innings_no: int
    booster: lgb.Booster
    calibration: Platt

    @property
    def features(self) -> list[str]:
        return FEATURES[self.innings_no]

    def matrix(self, states: pd.DataFrame) -> FloatArray:
        return np.asarray(states[self.features].to_numpy(dtype=np.float64), dtype=np.float64)

    def raw_logit(self, states: pd.DataFrame) -> FloatArray:
        return np.asarray(
            self.booster.predict(self.matrix(states), raw_score=True), dtype=np.float64
        )

    def predict(self, states: pd.DataFrame) -> FloatArray:
        return sigmoid(self.calibration(self.raw_logit(states)))

    def explain(self, states: pd.DataFrame) -> tuple[FloatArray, FloatArray]:
        """Calibrated win probability and each concept group's share of it, in points.

        Group points sum to ``100 * (p - p_base)``, where ``p_base`` is the
        model's average prediction: "how this moment differs from a typical one".
        """
        contrib = np.asarray(
            self.booster.predict(self.matrix(states), pred_contrib=True), dtype=np.float64
        )
        a = self.calibration.a
        raw = contrib.sum(axis=1)
        logit_p = self.calibration(raw)
        logit_0 = self.calibration(contrib[:, -1])
        p, p0 = sigmoid(logit_p), sigmoid(logit_0)
        gap = logit_p - logit_0
        safe = np.where(np.abs(gap) > 1e-9, gap, 1.0)
        scale = np.where(np.abs(gap) > 1e-9, (p - p0) / safe, p * (1 - p))
        points = 100.0 * a * contrib[:, :-1] * scale[:, None]
        index = {name: i for i, name in enumerate(self.features)}
        grouped = np.zeros((len(states), len(GROUP_KEYS)))
        for g, key in enumerate(GROUP_KEYS):
            cols = [index[f] for f in GROUPS[key][self.innings_no]]
            if cols:
                grouped[:, g] = points[:, cols].sum(axis=1)
        return p, grouped

    def base_probability(self) -> float:
        """The model's average prediction (the reference point for explanations)."""
        probe = pd.DataFrame([dict.fromkeys(self.features, 0.0)])
        contrib = np.asarray(self.booster.predict(probe.to_numpy(), pred_contrib=True))
        base = float(contrib[0, -1])
        return float(sigmoid(self.calibration(np.array([base])))[0])


@dataclass
class WinProbabilityModel:
    version: str
    innings: dict[int, InningsModel]
    manifest: dict[str, Any]

    def score(self, states: pd.DataFrame) -> pd.DataFrame:
        """Batting side's win probability and grouped explanation for every state."""
        out = pd.DataFrame(index=states.index)
        out["wp_batting"] = np.nan
        for key in GROUP_KEYS:
            out[f"pts_{key}"] = np.nan
        for number, model in self.innings.items():
            mask = (states["innings_no"] == number).to_numpy()
            if not mask.any():
                continue
            p, grouped = model.explain(states.loc[mask])
            out.loc[mask, "wp_batting"] = p
            out.loc[mask, [f"pts_{k}" for k in GROUP_KEYS]] = grouped
        return out

    # ------------------------------------------------------------ persistence

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        calibration = {}
        for number, model in self.innings.items():
            model.booster.save_model(str(directory / f"innings{number}.txt"))
            calibration[str(number)] = {"a": model.calibration.a, "b": model.calibration.b}
        manifest = {**self.manifest, "version": self.version, "calibration": calibration}
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

    @classmethod
    def load(cls, directory: Path) -> WinProbabilityModel:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        innings = {}
        for number in (1, 2):
            params = manifest["calibration"][str(number)]
            booster = lgb.Booster(model_file=str(directory / f"innings{number}.txt"))
            if booster.feature_name() != FEATURES[number]:
                raise ValueError(
                    f"model {directory} innings {number} was trained on different features"
                )
            innings[number] = InningsModel(number, booster, Platt(params["a"], params["b"]))
        return cls(version=manifest["version"], innings=innings, manifest=manifest)


def terminal_probability(
    *,
    innings_no: int,
    runs: int,
    wickets: int,
    legal_balls: int,
    max_balls: int,
    target: int | None,
) -> float | None:
    """Rule layer: the chasing side's result once a chase is mathematically over."""
    if innings_no != 2 or target is None:
        return None
    if runs >= target:
        return 1.0
    if wickets >= 10 or legal_balls >= max_balls:
        return 0.5 if runs == target - 1 else 0.0
    return None


def round_points(values: FloatArray) -> list[float]:
    return [0.0 if math.isnan(v) else round(float(v), 1) for v in values]
