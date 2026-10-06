"""Ball-outcome model: what happens on the next ball a batter faces.

Seven outcomes for every ball faced (wides are not faced): a dot, 1, 2, 3
(including the rare 5), 4, 6, or the batter dismissed by the bowler. Run outs
count as the runs completed, because they say little about the matchup.

The model is a multinomial logistic regression. The match situation enters as
a handful of one-hot groups (phase and innings, wickets down, how set the
batter is, batter hand against bowler type, chase pressure) plus the scoring
era. Every batter and every bowler gets their own coefficient per outcome,
penalised towards zero, which is a ridge (random-effects style) estimate of
their skill: a newcomer starts at average and earns an effect ball by ball.

The fitted model is a table of additive terms, so the API can evaluate it with
plain arithmetic and never imports an ML library (ADR-0004).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression

from criciq_core.phases import model_phases
from criciq_ml.data import check_formats

FloatArray = npt.NDArray[np.float64]

CLASSES = ("dot", "one", "two", "three", "four", "six", "out")
RUNS = np.array([0, 1, 2, 3, 4, 6, 0], dtype=float)
OUT = CLASSES.index("out")
DOT = CLASSES.index("dot")
BOUNDARY = [CLASSES.index("four"), CLASSES.index("six")]

# League runs per ball faced over this many previous matches: the scoring era.
ENV_WINDOW = 60
ENV_DEFAULT = 1.2

PHASES = tuple(p.key for p in sorted(model_phases().phases, key=lambda p: p.first_over))

# One-hot groups describing the situation; each row belongs to one level per group.
GROUPS: dict[str, tuple[str, ...]] = {
    "phase": tuple(f"{p}_{i}" for i in (1, 2) for p in PHASES),
    "wickets": ("0-1", "2-3", "4-5", "6+"),
    "settled": ("0-5", "6-15", "16-30", "31+"),
    "matchup": ("right_pace", "right_spin", "left_pace", "left_spin"),
    "pressure": ("none", "low", "par", "high", "extreme"),
}


def _balls_sql() -> str:
    phase = model_phases().sql_case("d.over_no")
    return f"""
    WITH outs AS (
        SELECT match_id, innings_no, seq_no,
               count(*) FILTER (WHERE is_dismissal) AS dismissals,
               bool_or(bowler_credited) AS bowler_out
        FROM wickets GROUP BY ALL
    )
    SELECT d.match_id, d.innings_no, d.seq_no, m.match_order, s.year AS season,
           {phase} AS phase, d.batter_id, d.bowler_id,
           coalesce(pb.batting_hand, 'unknown') AS batting_hand,
           coalesce(pw.bowling_type, 'unknown') AS bowling_type,
           d.runs_batter, coalesce(o.bowler_out, false) AS bowler_out,
           d.team_runs - d.runs_total AS runs_before,
           d.team_wickets - coalesce(o.dismissals, 0) AS wickets_before,
           d.legal_ball_no - d.is_legal::INTEGER AS balls_before,
           i.target_runs,
           coalesce(i.target_balls, m.scheduled_overs * m.balls_per_over) AS max_balls,
           (row_number() OVER (PARTITION BY d.match_id, d.innings_no, d.batter_id
                               ORDER BY d.seq_no) - 1)::INTEGER AS batter_balls
    FROM deliveries d
    JOIN innings i USING (match_id, innings_no)
    JOIN matches m USING (match_id)
    JOIN seasons s USING (season_id)
    LEFT JOIN outs o USING (match_id, innings_no, seq_no)
    LEFT JOIN players pb ON pb.player_id = d.batter_id
    LEFT JOIN players pw ON pw.player_id = d.bowler_id
    WHERE NOT i.is_super_over AND d.extras_wides = 0
    ORDER BY m.match_order, d.innings_no, d.seq_no
    """


def outcome_index(runs_batter: npt.ArrayLike, bowler_out: npt.ArrayLike) -> npt.NDArray[np.int64]:
    runs = np.asarray(runs_batter)
    index = np.select(
        [runs == 0, runs == 1, runs == 2, (runs == 3) | (runs == 5), runs == 4, runs >= 6],
        [0, 1, 2, 3, 4, 5],
        default=0,
    )
    return np.where(np.asarray(bowler_out, dtype=bool), OUT, index).astype(np.int64)


def _bucket(values: pd.Series, edges: list[float], labels: tuple[str, ...]) -> pd.Series:
    return pd.Series(
        pd.cut(values, [-np.inf, *edges, np.inf], labels=list(labels), right=False).astype(str),
        index=values.index,
    )


def load_balls(database: Path) -> pd.DataFrame:
    """Every ball faced outside super overs, with its situation and outcome."""
    con = duckdb.connect(str(database), read_only=True)
    try:
        check_formats(con)
        balls = con.execute(_balls_sql()).df()
    finally:
        con.close()
    return add_situation(balls)


def add_situation(balls: pd.DataFrame) -> pd.DataFrame:
    """Outcome, scoring era (as of the previous matches) and situation levels."""
    balls = balls.copy()
    balls["outcome"] = outcome_index(balls["runs_batter"], balls["bowler_out"])

    per_match = (
        balls.groupby("match_order")
        .agg(runs=("runs_batter", "sum"), balls=("runs_batter", "size"))
        .sort_index()
    )
    rolled = per_match.rolling(ENV_WINDOW, min_periods=1).sum().shift(1)
    env = (rolled["runs"] / rolled["balls"]).fillna(ENV_DEFAULT)
    balls["env"] = balls["match_order"].map(env).astype(float)

    balls["g_phase"] = balls["phase"] + "_" + balls["innings_no"].astype(str)
    balls["g_wickets"] = _bucket(balls["wickets_before"], [2, 4, 6], GROUPS["wickets"])
    balls["g_settled"] = _bucket(balls["batter_balls"], [6, 16, 31], GROUPS["settled"])
    balls["g_matchup"] = balls["batting_hand"] + "_" + balls["bowling_type"]

    remaining = (balls["max_balls"] - balls["balls_before"]).clip(lower=1)
    required = (balls["target_runs"] - balls["runs_before"]) * 6 / remaining
    relative = required / (balls["env"] * 6)
    pressure = _bucket(relative.fillna(0), [0.8, 1.1, 1.4], GROUPS["pressure"][1:])
    balls["g_pressure"] = np.where(balls["innings_no"] == 2, pressure, "none")
    return balls


# --------------------------------------------------------------------------- design


@dataclass(frozen=True)
class Design:
    """Column layout: situation levels, the era, then batters and bowlers."""

    context: tuple[str, ...]
    batters: tuple[str, ...]
    bowlers: tuple[str, ...]
    env_mean: float
    env_std: float
    # Candidate: a separate effect per player and phase on top of the overall one.
    phase_players: bool = False

    @classmethod
    def from_training(
        cls, balls: pd.DataFrame, min_balls: int = 1, phase_players: bool = False
    ) -> Design:
        context = tuple(f"{g}={level}" for g, levels in GROUPS.items() for level in levels)
        bat = balls["batter_id"].value_counts()
        bowl = balls["bowler_id"].value_counts()
        log_env = np.log(balls["env"].to_numpy())
        return cls(
            context=context,
            batters=tuple(sorted(bat[bat >= min_balls].index)),
            bowlers=tuple(sorted(bowl[bowl >= min_balls].index)),
            env_mean=float(log_env.mean()),
            env_std=float(log_env.std() or 1.0),
            phase_players=phase_players,
        )

    def player_blocks(self) -> list[tuple[str, str, tuple[str, ...], str | None]]:
        """(term prefix, id column, ids, phase) for each block of player columns."""
        blocks: list[tuple[str, str, tuple[str, ...], str | None]] = [
            ("batter", "batter_id", self.batters, None),
            ("bowler", "bowler_id", self.bowlers, None),
        ]
        if self.phase_players:
            for phase in PHASES:
                blocks.append((f"batter@{phase}", "batter_id", self.batters, phase))
                blocks.append((f"bowler@{phase}", "bowler_id", self.bowlers, phase))
        return blocks

    def matrix(self, balls: pd.DataFrame, player_scale: float) -> sparse.csr_matrix:
        n = len(balls)
        rows: list[npt.NDArray[np.int64]] = []
        cols: list[npt.NDArray[np.int64]] = []
        vals: list[FloatArray] = []
        index = {name: i for i, name in enumerate(self.context)}
        for group in GROUPS:
            keys = (group + "=" + balls[f"g_{group}"].astype(str)).map(index)
            known = keys.notna().to_numpy()
            rows.append(np.arange(n)[known])
            cols.append(keys[known].astype(np.int64).to_numpy())
            vals.append(np.ones(known.sum()))
        env_col = len(self.context)
        rows.append(np.arange(n))
        cols.append(np.full(n, env_col))
        vals.append((np.log(balls["env"].to_numpy()) - self.env_mean) / self.env_std)
        offset = env_col + 1
        for _, column, ids, phase in self.player_blocks():
            lookup = {p: i for i, p in enumerate(ids)}
            keys = balls[column].map(lookup)
            known = keys.notna().to_numpy()
            if phase is not None:
                known = known & (balls["phase"] == phase).to_numpy()
            rows.append(np.arange(n)[known])
            cols.append(keys[known].astype(np.int64).to_numpy() + offset)
            vals.append(np.full(known.sum(), player_scale))
            offset += len(ids)
        return sparse.csr_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(n, offset),
        )


def softmax(logits: FloatArray) -> FloatArray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    out: FloatArray = e / e.sum(axis=1, keepdims=True)
    return out


class BallOutcomeModel:
    """Additive terms per outcome: intercept + situation + era + batter + bowler."""

    def __init__(self, terms: dict[str, FloatArray], manifest: dict[str, Any]) -> None:
        self.terms = terms
        self.manifest = manifest

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @classmethod
    def fit(
        cls,
        balls: pd.DataFrame,
        *,
        player_scale: float,
        c: float,
        max_iter: int,
        manifest: dict[str, Any] | None = None,
        phase_players: bool = False,
    ) -> BallOutcomeModel:
        design = Design.from_training(balls, phase_players=phase_players)
        x = design.matrix(balls, player_scale)
        clf = LogisticRegression(C=c, max_iter=max_iter, tol=1e-6)
        clf.fit(x, balls["outcome"].to_numpy())
        coef = np.zeros((x.shape[1], len(CLASSES)))
        coef[:, clf.classes_] = clf.coef_.T
        intercept = np.zeros(len(CLASSES))
        intercept[clf.classes_] = clf.intercept_
        terms: dict[str, FloatArray] = {"intercept": intercept}
        for i, name in enumerate(design.context):
            terms[name] = coef[i]
        terms["env"] = coef[len(design.context)]
        offset = len(design.context) + 1
        for prefix, _, ids, _ in design.player_blocks():
            for i, player in enumerate(ids):
                effect = coef[offset + i] * player_scale
                if prefix in ("batter", "bowler") or np.abs(effect).max() > 1e-6:
                    terms[f"{prefix}={player}"] = effect
            offset += len(ids)
        info = {
            "classes": list(CLASSES),
            "env_mean": design.env_mean,
            "env_std": design.env_std,
            "player_scale": player_scale,
            "c": c,
            **(manifest or {}),
        }
        return cls(terms, info)

    def logits(self, balls: pd.DataFrame) -> FloatArray:
        out = np.tile(self.terms["intercept"], (len(balls), 1))
        for group in GROUPS:
            keys = group + "=" + balls[f"g_{group}"].astype(str)
            out += np.stack([self.terms.get(k, np.zeros(len(CLASSES))) for k in keys])
        era = (np.log(balls["env"].to_numpy()) - self.manifest["env_mean"]) / self.manifest[
            "env_std"
        ]
        out += np.outer(era, self.terms["env"])
        blocks: dict[str, dict[str, FloatArray]] = {}
        for key, value in self.terms.items():
            if key.startswith(("batter", "bowler")):
                prefix, player = key.split("=", 1)
                blocks.setdefault(prefix, {})[player] = value
        zero = np.zeros(len(CLASSES))
        for prefix, effects in blocks.items():
            role, _, phase = prefix.partition("@")
            ids = balls[f"{role}_id"].to_numpy()
            rows = np.stack([effects.get(p, zero) for p in ids])
            if phase:
                rows[(balls["phase"] != phase).to_numpy()] = 0.0
            out += rows
        return out

    def predict(self, balls: pd.DataFrame) -> FloatArray:
        return softmax(self.logits(balls))

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {k: [round(float(x), 6) for x in v] for k, v in sorted(self.terms.items())}
        (directory / "terms.json").write_text(
            json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
        )
        (directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @classmethod
    def load(cls, directory: Path) -> BallOutcomeModel:
        raw = json.loads((directory / "terms.json").read_text(encoding="utf-8"))
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        return cls({k: np.asarray(v, dtype=float) for k, v in raw.items()}, manifest)


# --------------------------------------------------------------------------- metrics


def log_loss(probs: FloatArray, outcome: npt.ArrayLike) -> float:
    y = np.asarray(outcome)
    picked = np.clip(probs[np.arange(len(y)), y], 1e-12, 1.0)
    return float(-np.log(picked).mean())


def brier(probs: FloatArray, outcome: npt.ArrayLike) -> float:
    y = np.asarray(outcome)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(y)), y] = 1.0
    return float(((probs - onehot) ** 2).sum(axis=1).mean())


class MarginalBaseline:
    """Outcome frequencies by phase, innings and wickets down (no players, no era)."""

    def __init__(self, balls: pd.DataFrame) -> None:
        keys = ["g_phase", "g_wickets"]
        counts = (
            balls.groupby(keys)["outcome"]
            .value_counts()
            .unstack(fill_value=0)
            .reindex(columns=range(len(CLASSES)), fill_value=0)
        )
        smoothed = counts.to_numpy(dtype=float) + 1.0
        self.table = pd.DataFrame(
            smoothed / smoothed.sum(axis=1, keepdims=True), index=counts.index
        )
        overall = np.bincount(balls["outcome"], minlength=len(CLASSES)) + 1.0
        self.overall = overall / overall.sum()

    def predict(self, balls: pd.DataFrame) -> FloatArray:
        idx = pd.MultiIndex.from_frame(balls[["g_phase", "g_wickets"]])
        found = self.table.reindex(idx)
        out: FloatArray = found.to_numpy(dtype=float, copy=True)
        missing = np.isnan(out).any(axis=1)
        out[missing] = self.overall
        return out


# --------------------------------------------------------------------------- matchups


def dirichlet_multinomial_loglik(kappa: float, counts: FloatArray, prior: FloatArray) -> float:
    """Log likelihood (up to a constant) of pair counts under Dirichlet(kappa * prior)."""
    from scipy.special import gammaln

    alpha = kappa * prior
    totals = counts.sum(axis=1)
    return float(
        (
            gammaln(kappa)
            - gammaln(totals + kappa)
            + (gammaln(counts + alpha) - gammaln(alpha)).sum(axis=1)
        ).sum()
    )


def fit_kappa(counts: FloatArray, prior: FloatArray) -> float:
    """Empirical-Bayes prior strength, in balls, for head-to-head records.

    ``counts`` are each pair's outcome counts and ``prior`` the outcome
    distribution the model expects for those same balls. The larger kappa,
    the less a pair's history differs from what the two players' overall
    records predict.
    """
    from scipy.optimize import minimize_scalar

    prior = np.clip(prior, 1e-9, None)
    prior = prior / prior.sum(axis=1, keepdims=True)
    result = minimize_scalar(
        lambda log_k: -dirichlet_multinomial_loglik(float(np.exp(log_k)), counts, prior),
        bounds=(np.log(1.0), np.log(1e6)),
        method="bounded",
    )
    return float(np.exp(result.x))


def pair_counts(balls: pd.DataFrame, probs: FloatArray) -> pd.DataFrame:
    """Observed and expected outcome counts per batter-bowler pair."""
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(balls)), balls["outcome"].to_numpy()] = 1.0
    frame = pd.DataFrame(
        np.hstack([onehot, probs]),
        columns=[f"n_{c}" for c in CLASSES] + [f"e_{c}" for c in CLASSES],
    )
    frame["batter_id"] = balls["batter_id"].to_numpy()
    frame["bowler_id"] = balls["bowler_id"].to_numpy()
    return frame.groupby(["batter_id", "bowler_id"]).sum()
