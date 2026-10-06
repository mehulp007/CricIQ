"""The pooled T20 models against v1 on the IPL's test seasons.

v2 trains on every T20 competition at once. Whether that helps the IPL is
measured, not assumed: v1's headline test predictions (fit on the IPL alone
with v1's tuned settings) are rebuilt exactly, and compared ball by ball with
the pooled model's on the same IPL test balls, resampling whole matches for a
95% interval. The pooled model serves the IPL only if it is no worse there;
otherwise the IPL keeps v1 and the pooled model serves the other competitions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from criciq_ml import metrics
from criciq_ml.ball_outcome import BallOutcomeModel
from criciq_ml.ball_outcome import brier as ball_brier
from criciq_ml.ball_outcome import log_loss as ball_log_loss
from criciq_ml.config import WinProbabilityConfig
from criciq_ml.features import FEATURES, LABEL
from criciq_ml.model import sigmoid
from criciq_ml.projection import FEATURES as PROJECTION_FEATURES
from criciq_ml.projection import (
    HIGH80,
    LEVELS,
    LOW80,
    MEDIAN,
    projection_frame,
    raw_ratios,
    to_totals,
)
from criciq_ml.projection import trainable as projection_trainable
from criciq_ml.projection_training import ProjectionConfig, _fit_and_calibrate, pinball
from criciq_ml.training import Method, _fit_for, evaluable, raw_logit, trainable

KEYS = ["match_id", "innings_no", "seq_no"]


def v1_win_probability(
    states: pd.DataFrame, cfg: WinProbabilityConfig, evaluation: dict[str, Any]
) -> pd.DataFrame:
    """v1's headline test predictions, rebuilt from its evaluation record.

    ``states`` are the IPL's own (v1 features); ``cfg`` supplies the shared
    LightGBM settings and ``evaluation`` the tuned choices, rounds and
    calibration method v1 recorded.
    """
    # v1 was fit with 4 threads; LightGBM is reproducible only with the same count.
    base = {**cfg.lightgbm.base, "num_threads": 4}
    cfg = cfg.model_copy(update={"lightgbm": cfg.lightgbm.model_copy(update={"base": base})})
    labelled = trainable(states)
    tests = evaluation["splits"]["test"]
    first_test = min(tests)
    method: Method = evaluation["calibration"]["method"]
    frames = []
    for number in (1, 2):
        data = labelled[labelled["innings_no"] == number]
        test = evaluable(data[data["season"].isin(tests)])
        choice = evaluation["tuning"]["chosen"][str(number)]
        rounds = int(evaluation["tuning"]["rounds"][str(number)])
        fitted, platt = _fit_for(
            cfg, data, number, choice, rounds, FEATURES[number], before=first_test, method=method
        )
        p = sigmoid(platt(raw_logit(fitted, test, FEATURES[number])))
        frames.append(test[KEYS].assign(y=test[LABEL].to_numpy(), p=p))
    return pd.concat(frames, ignore_index=True)


def compare(
    v1: pd.DataFrame, v2: pd.DataFrame, *, v1_version: str, v2_version: str
) -> dict[str, Any]:
    """Both models' test metrics on the balls both scored, and v2's gain over v1."""
    joined = v1.merge(v2[[*KEYS, "p"]], on=KEYS, suffixes=("_v1", "_v2"), validate="1:1")
    if len(joined) != len(v1):
        raise ValueError(f"v2 scored {len(joined)} of v1's {len(v1)} test balls")
    y = joined["y"].to_numpy()
    p1, p2 = joined["p_v1"].to_numpy(), joined["p_v2"].to_numpy()
    groups = joined["match_id"].to_numpy()
    gain = metrics.paired_bootstrap(groups, y, p2, p1)
    return {
        "competition": "IPL",
        "matches": int(joined["match_id"].nunique()),
        "v1": {"version": v1_version, **metrics.summarize(y, p1)},
        "v2": {"version": v2_version, **metrics.summarize(y, p2)},
        "v2_gain": gain,
        "no_worse": bool(metrics.log_loss(y, p2) <= metrics.log_loss(y, p1)),
        "better": bool(gain["ci_low"] > 0),
        "by_innings": [
            {
                "innings_no": number,
                "v1": metrics.summarize(y[mask], p1[mask]),
                "v2": metrics.summarize(y[mask], p2[mask]),
            }
            for number in (1, 2)
            if (mask := (joined["innings_no"] == number).to_numpy()).any()
        ],
    }


def serves_ipl(comparison: dict[str, Any]) -> bool:
    """The gate: the pooled model serves the IPL only if it is no worse there."""
    return bool(comparison["no_worse"])


def check_reproduced(rebuilt: pd.DataFrame, evaluation: dict[str, Any]) -> None:
    """Rebuilt v1 predictions must score exactly what v1 recorded."""
    recorded = float(evaluation["test"]["model"]["log_loss"])
    found = metrics.log_loss(rebuilt["y"].to_numpy(), rebuilt["p"].to_numpy())
    if not np.isclose(found, recorded, atol=1e-9):
        raise ValueError(f"v1 rebuilt to test log loss {found:.6f}, recorded {recorded:.6f}")


# ---------------------------------------------------------------- score projection


def v1_projection(
    states: pd.DataFrame, cfg: ProjectionConfig, evaluation: dict[str, Any]
) -> pd.DataFrame:
    """v1's headline test quantiles, rebuilt from its evaluation record."""
    base = {**cfg.lightgbm["base"], "num_threads": 4}
    cfg = cfg.model_copy(update={"lightgbm": {**cfg.lightgbm, "base": base}})
    data = projection_trainable(projection_frame(states))
    tests = evaluation["splits"]["test"]
    test = data[data["season"].isin(tests)]
    choice = evaluation["tuning"]["chosen"]
    rounds = {float(k): int(v) for k, v in evaluation["tuning"]["rounds"].items()}
    boosters, shifts = _fit_and_calibrate(
        cfg, data, choice, rounds, PROJECTION_FEATURES, before=min(tests)
    )
    q = to_totals(raw_ratios(boosters, test, PROJECTION_FEATURES), test, shifts)
    return test[["match_id", "seq_no", "final_runs", "runs"]].assign(quantiles=list(q))


def check_projection_reproduced(rebuilt: pd.DataFrame, evaluation: dict[str, Any]) -> None:
    recorded = float(evaluation["test"]["model"]["pinball"])
    found = pinball(np.vstack(rebuilt["quantiles"].to_numpy()), rebuilt["final_runs"].to_numpy())
    if not np.isclose(found, recorded, atol=1e-9):
        raise ValueError(f"v1 rebuilt to test pinball {found:.6f}, recorded {recorded:.6f}")


def _pinball_rows(q: np.ndarray, y: np.ndarray) -> np.ndarray:
    losses = [
        np.maximum(level * (y - q[:, i]), (level - 1) * (y - q[:, i]))
        for i, level in enumerate(LEVELS)
    ]
    return np.asarray(np.mean(losses, axis=0), dtype=np.float64)


def compare_projection(
    v1: pd.DataFrame,
    v2: pd.DataFrame,
    *,
    v1_version: str,
    v2_version: str,
    band: tuple[float, float] = (0.75, 0.85),
    seed: int = 7,
) -> dict[str, Any]:
    """Both projections on the IPL test balls both scored; v2's pinball gain over v1.

    The pooled projection serves the IPL only if it is no worse there on pinball loss
    and its 80% range covers the IPL's totals within ``band``, the coverage the
    projection's promotion gate requires.
    """
    keys = ["match_id", "seq_no"]
    joined = v1.merge(v2[[*keys, "quantiles"]], on=keys, suffixes=("_v1", "_v2"), validate="1:1")
    if len(joined) != len(v1):
        raise ValueError(f"v2 projected {len(joined)} of v1's {len(v1)} test balls")
    y = joined["final_runs"].to_numpy(dtype=np.float64)
    q1 = np.vstack(joined["quantiles_v1"].to_numpy())
    q2 = np.vstack(joined["quantiles_v2"].to_numpy())

    def summary(q: np.ndarray) -> dict[str, Any]:
        inside = (y >= q[:, LOW80]) & (y <= q[:, HIGH80])
        return {
            "rows": len(y),
            "pinball": pinball(q, y),
            "mae": float(np.mean(np.abs(q[:, MEDIAN] - y))),
            "coverage80": float(inside.mean()),
            "width80": float(np.mean(q[:, HIGH80] - q[:, LOW80])),
        }

    # Pinball gain per innings (match), resampled by match for a 95% interval.
    diff = _pinball_rows(q1, y) - _pinball_rows(q2, y)
    ids, inverse = np.unique(joined["match_id"].to_numpy(), return_inverse=True)
    sums = np.bincount(inverse, weights=diff)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(1000, len(ids)))
    stats = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    gain = {
        "improvement": float(sums.sum() / counts.sum()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "innings": len(ids),
    }
    s1, s2 = summary(q1), summary(q2)
    return projection_verdict(
        {
            "competition": "IPL",
            "v1": {"version": v1_version, **s1},
            "v2": {"version": v2_version, **s2},
            "v2_gain": gain,
            "better": bool(gain["ci_low"] > 0),
        },
        band,
    )


def projection_verdict(result: dict[str, Any], band: tuple[float, float]) -> dict[str, Any]:
    """Whether the pooled projection serves the IPL (see ``compare_projection``)."""
    low, high = band
    covered = low <= result["v2"]["coverage80"] <= high
    no_worse = result["v2"]["pinball"] <= result["v1"]["pinball"]
    return {
        **result,
        "coverage_band": [low, high],
        "coverage_ok": bool(covered),
        "no_worse": bool(no_worse and covered),
    }


# ---------------------------------------------------------------- ball outcome

BALL_KEYS = ["match_id", "innings_no", "seq_no"]


def v1_ball_outcome(
    balls: pd.DataFrame,
    evaluation: dict[str, Any],
    manifest: dict[str, Any],
    max_iter: int,
) -> pd.DataFrame:
    """v1's headline test probabilities, refit with the settings it recorded."""
    tests = evaluation["splits"]["test"]
    train = balls[balls["season"] < min(tests)]
    test = balls[balls["season"].isin(tests)]
    model = BallOutcomeModel.fit(
        train,
        player_scale=float(evaluation["tuning"]["player_scale"]),
        c=float(manifest["c"]),
        max_iter=max_iter,
        phase_players=bool(evaluation["tuning"]["phase_players"]),
    )
    return test[[*BALL_KEYS, "outcome"]].assign(probs=list(model.predict(test)))


def check_ball_reproduced(rebuilt: pd.DataFrame, evaluation: dict[str, Any]) -> None:
    recorded = float(evaluation["test"]["model"]["log_loss"])
    found = ball_log_loss(np.vstack(rebuilt["probs"].to_numpy()), rebuilt["outcome"].to_numpy())
    if not np.isclose(found, recorded, atol=1e-7):
        raise ValueError(f"v1 rebuilt to test log loss {found:.7f}, recorded {recorded:.7f}")


def compare_ball_outcome(
    v1: pd.DataFrame, v2: pd.DataFrame, *, v1_version: str, v2_version: str, seed: int = 7
) -> dict[str, Any]:
    """Both ball models on the IPL test balls both scored; v2's log-loss gain over v1."""
    joined = v1.merge(
        v2[[*BALL_KEYS, "probs"]], on=BALL_KEYS, suffixes=("_v1", "_v2"), validate="1:1"
    )
    if len(joined) != len(v1):
        raise ValueError(f"v2 scored {len(joined)} of v1's {len(v1)} test balls")
    y = joined["outcome"].to_numpy()
    p1 = np.vstack(joined["probs_v1"].to_numpy())
    p2 = np.vstack(joined["probs_v2"].to_numpy())
    rows = np.arange(len(y))
    loss1 = -np.log(np.clip(p1[rows, y], 1e-12, 1.0))
    loss2 = -np.log(np.clip(p2[rows, y], 1e-12, 1.0))
    ids, inverse = np.unique(joined["match_id"].to_numpy(), return_inverse=True)
    sums = np.bincount(inverse, weights=loss1 - loss2)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(1000, len(ids)))
    stats = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    gain = {
        "improvement": float(sums.sum() / counts.sum()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "matches": len(ids),
    }
    s1 = {"balls": len(y), "log_loss": float(loss1.mean()), "brier": ball_brier(p1, y)}
    s2 = {"balls": len(y), "log_loss": float(loss2.mean()), "brier": ball_brier(p2, y)}
    return {
        "competition": "IPL",
        "v1": {"version": v1_version, **s1},
        "v2": {"version": v2_version, **s2},
        "v2_gain": gain,
        "no_worse": bool(s2["log_loss"] <= s1["log_loss"]),
        "better": bool(gain["ci_low"] > 0),
    }
