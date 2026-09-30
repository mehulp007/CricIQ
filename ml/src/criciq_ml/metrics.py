"""Probabilistic evaluation metrics.

Labels may be 0, 1 or 0.5 (a tied match), so log loss and Brier score are
computed directly rather than through classification helpers. Ball-level
accuracy is deliberately absent: it says nothing about probability quality.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import roc_auc_score

EPS = 1e-6
FloatArray = NDArray[np.float64]


def log_loss(y: FloatArray, p: FloatArray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y: FloatArray, p: FloatArray) -> float:
    return float(np.mean((p - y) ** 2))


def reliability(y: FloatArray, p: FloatArray, bins: int = 10) -> list[dict[str, float]]:
    """Mean predicted vs observed win rate in equal-width probability bins."""
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    table = []
    for b in range(bins):
        mask = index == b
        if not mask.any():
            continue
        table.append(
            {
                "lower": float(edges[b]),
                "upper": float(edges[b + 1]),
                "predicted": float(p[mask].mean()),
                "observed": float(y[mask].mean()),
                "count": int(mask.sum()),
            }
        )
    return table


def ece(y: FloatArray, p: FloatArray, bins: int = 10) -> float:
    """Expected calibration error: count-weighted gap between predicted and observed."""
    total = len(y)
    return float(
        sum(
            b["count"] / total * abs(b["predicted"] - b["observed"])
            for b in reliability(y, p, bins)
        )
    )


def auc(y: FloatArray, p: FloatArray) -> float | None:
    decided = (y == 0) | (y == 1)
    if len(np.unique(y[decided])) < 2:
        return None
    return float(roc_auc_score(y[decided], p[decided]))


def summarize(y: FloatArray, p: FloatArray) -> dict[str, Any]:
    return {
        "rows": len(y),
        "log_loss": log_loss(y, p),
        "brier": brier(y, p),
        "ece": ece(y, p),
        "auc": auc(y, p),
    }


def paired_bootstrap(
    groups: NDArray[np.int64],
    y: FloatArray,
    p_model: FloatArray,
    p_base: FloatArray,
    *,
    resamples: int = 1000,
    seed: int = 7,
) -> dict[str, float]:
    """Log-loss improvement over a baseline with a 95% interval, resampling whole matches.

    Deliveries within a match are strongly correlated, so the match (not the
    ball) is the unit of resampling. Positive = the model is better.
    """
    p_model = np.clip(p_model, EPS, 1 - EPS)
    p_base = np.clip(p_base, EPS, 1 - EPS)
    loss_m = -(y * np.log(p_model) + (1 - y) * np.log(1 - p_model))
    loss_b = -(y * np.log(p_base) + (1 - y) * np.log(1 - p_base))
    ids, inverse = np.unique(groups, return_inverse=True)
    diff_sum = np.bincount(inverse, weights=loss_b - loss_m)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(resamples, len(ids)))
    stats = diff_sum[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {
        "improvement": float(diff_sum.sum() / counts.sum()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "matches": len(ids),
    }
